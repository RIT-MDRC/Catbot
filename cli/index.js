#! /usr/bin/env node

import { existsSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn, spawnSync } from 'node:child_process';

import yargs from 'yargs';
import { hideBin } from 'yargs/helpers';

const PACKAGE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const FOUNDATION_ROOT = path.join('src', 'foundation', 'foundation');
const ROS_SETUP = '/opt/ros/humble/setup.bash';

export function runtimeDirectory() {
	const dataHome = process.env.XDG_DATA_HOME ?? path.join(os.homedir(), '.local', 'share');
	return path.join(dataHome, 'catbot');
}

export function projectRoot(dev = false) {
	return dev ? process.cwd() : PACKAGE_ROOT;
}

export function runtimeEnvironment() {
	return path.join(runtimeDirectory(), '.venv');
}

function commandExists(command) {
	return spawnSync(command, ['--version'], { stdio: 'ignore' }).status === 0;
}

function run(command, args, options = {}) {
	const result = spawnSync(command, args, { stdio: 'inherit', ...options });
	if (result.error) {
		console.error(`Unable to run ${command}: ${result.error.message}`);
		return 1;
	}
	return result.status ?? 1;
}

export function uvEnvironment(root) {
	return {
		...process.env,
		UV_PROJECT_ENVIRONMENT: runtimeEnvironment(),
		CATBOT_PROJECT_ROOT: root,
	};
}

function setup(args) {
	if (!commandExists('uv')) {
		console.error('uv is required. Install it from https://docs.astral.sh/uv/.');
		process.exitCode = 1;
		return;
	}

	const root = projectRoot(args.dev);
	if (!existsSync(path.join(root, 'pyproject.toml')) || !existsSync(path.join(root, 'uv.lock'))) {
		console.error(`Catbot uv project files were not found in ${root}.`);
		process.exitCode = 1;
		return;
	}

	const envPath = runtimeEnvironment();
	if (process.platform === 'linux' && process.arch === 'arm64' && !existsSync(ROS_SETUP)) {
		console.error(`ROS Humble setup was not found at ${ROS_SETUP}.`);
		process.exitCode = 1;
		return;
	}
	const isRosPi = process.platform === 'linux' && existsSync(ROS_SETUP);
	const pythonRequest = isRosPi ? '/usr/bin/python3' : '3.10';
	const venvArgs = ['venv', '--python', pythonRequest];
	if (isRosPi) {
		venvArgs.push('--system-site-packages');
	}
	if (args.reset) {
		venvArgs.push('--clear');
	}
	venvArgs.push(envPath);

	let status = 0;
	if (args.reset || !existsSync(path.join(envPath, 'pyvenv.cfg'))) {
		console.log(`Creating Catbot environment at ${envPath}`);
		status = run('uv', venvArgs);
		if (status !== 0) {
			process.exitCode = status;
			return;
		}
	} else {
		console.log(`Reusing Catbot environment at ${envPath}`);
	}

	console.log('Synchronizing locked Catbot dependencies');
	status = run('uv', ['sync', '--frozen', '--no-dev', '--project', root], {
		env: uvEnvironment(root),
	});
	if (status === 0 && isRosPi) {
		console.log('Building Catbot ROS interfaces');
		const rosRuntime = path.join(runtimeDirectory(), 'ros');
		status = run(
			'/bin/bash',
			[
				'-c',
				'source "$1" && shift && exec "$@"',
				'catbot',
				ROS_SETUP,
				'colcon',
				'--log-base',
				path.join(rosRuntime, 'log'),
				'build',
				'--base-paths',
				path.join(root, 'src'),
				'--build-base',
				path.join(rosRuntime, 'build'),
				'--install-base',
				path.join(rosRuntime, 'install'),
				'--packages-select',
				'catbot_interfaces',
			],
			{ env: uvEnvironment(root) },
		);
	}
	if (status === 0) {
		console.log('Catbot setup complete.');
	}
	process.exitCode = status;
}

function spawnUv(root, script, scriptArgs = []) {
	const envPath = runtimeEnvironment();
	if (!existsSync(path.join(envPath, 'pyvenv.cfg'))) {
		console.error('Catbot is not set up. Run `catbot setup` first.');
		process.exitCode = 1;
		return;
	}

	const uvArgs = [
		'run',
		'--frozen',
		'--no-dev',
		'--project',
		root,
		script,
		...scriptArgs,
	];
	const env = uvEnvironment(root);
	let child;
	if (process.platform === 'linux' && existsSync(ROS_SETUP)) {
		const workspaceSetup = path.join(runtimeDirectory(), 'ros', 'install', 'setup.bash');
		child = spawn(
			'/bin/bash',
			[
				'-c',
				'source "$1" && shift && if [ ! -f "$1" ]; then echo "Catbot ROS interfaces are not built. Run: catbot setup" >&2; exit 1; fi && source "$1" && shift && exec "$@"',
				'catbot',
				ROS_SETUP,
				workspaceSetup,
				'uv',
				...uvArgs,
			],
			{ env, stdio: 'inherit' },
		);
	} else {
		child = spawn('uv', uvArgs, { env, stdio: 'inherit' });
	}

	child.on('close', (code) => {
		process.exitCode = code ?? 1;
	});
	child.on('error', (error) => {
		console.error(`Failed to run Catbot: ${error.message}`);
		process.exitCode = 1;
	});
}

function resolveInside(base, requested) {
	const resolved = path.resolve(base, requested);
	if (resolved !== base && !resolved.startsWith(`${base}${path.sep}`)) {
		throw new Error(`Path must stay inside ${base}`);
	}
	return resolved;
}

function start(args) {
	const root = projectRoot(args.dev);
	const defaultScript = path.join(root, FOUNDATION_ROOT, 'main.py');
	const script = args.file
		? resolveInside(root, args.file.endsWith('.py') ? args.file : `${args.file}.py`)
		: defaultScript;
	spawnUv(root, script);
}

function sample(args) {
	const root = projectRoot(args.dev);
	const samplesRoot = path.join(root, FOUNDATION_ROOT, 'samples');
	const sampleName = args.file === 'motor-test' ? 'odrive_position_test' : args.file;
	const script = resolveInside(samplesRoot, `${sampleName}.py`);
	if (!existsSync(script)) {
		console.error(`Unknown sample: ${args.file}`);
		process.exitCode = 1;
		return;
	}

	const scriptArgs = [];
	if (args.file === 'motor-test') {
		if (args.motor) {
			scriptArgs.push('--motor', args.motor);
		}
		if (args.config) {
			scriptArgs.push('--config', path.resolve(args.config));
		}
	}
	spawnUv(root, script, scriptArgs);
}

yargs(hideBin(process.argv))
	.scriptName('catbot')
	.command({
		command: 'setup',
		describe: 'create or update the Catbot uv environment',
		builder: (command) =>
			command
				.option('D', {
					alias: 'dev',
					describe: 'use the current repository checkout',
					type: 'boolean',
					default: false,
				})
				.option('reset', {
					describe: 'recreate the Catbot environment before syncing',
					type: 'boolean',
					default: false,
				}),
		handler: setup,
	})
	.command({
		command: 'start',
		aliases: ['s'],
		describe: 'start the Catbot foundation node',
		builder: (command) =>
			command
				.option('f', {
					alias: 'file',
					describe: 'run a different Python file relative to the project root',
					type: 'string',
				})
				.option('D', {
					alias: 'dev',
					describe: 'use the current repository checkout',
					type: 'boolean',
					default: false,
				}),
		handler: start,
	})
	.command({
		command: 'sample <file>',
		aliases: ['smpl'],
		describe: 'run a Catbot hardware sample',
		builder: (command) =>
			command
				.positional('file', {
					describe: 'sample name; use motor-test for interactive ODrive control',
					type: 'string',
				})
				.option('motor', {
					describe: 'configured motor name or CAN axis ID for motor-test',
					type: 'string',
				})
				.option('config', {
					describe: 'configuration file for the motor-test sample',
					type: 'string',
				})
				.option('D', {
					alias: 'dev',
					describe: 'use the current repository checkout',
					type: 'boolean',
					default: false,
				}),
		handler: sample,
	})
	.demandCommand(1)
	.strict()
	.help()
	.parse();
