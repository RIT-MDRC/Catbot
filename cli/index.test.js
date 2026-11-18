import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const cli = path.join(path.dirname(fileURLToPath(import.meta.url)), 'index.js');

test('CLI help lists setup and sample commands', () => {
	const result = spawnSync(process.execPath, [cli, '--help'], { encoding: 'utf8' });
	assert.equal(result.status, 0, result.stderr);
	assert.match(result.stdout, /setup/);
	assert.match(result.stdout, /sample/);
});

test('motor test launches the listing path when --motor is omitted', (t) => {
	const directory = mkdtempSync(path.join(os.tmpdir(), 'catbot-cli-test-'));
	t.after(() => rmSync(directory, { recursive: true, force: true }));
	const runtime = path.join(directory, 'catbot');
	mkdirSync(path.join(runtime, '.venv'), { recursive: true });
	writeFileSync(path.join(runtime, '.venv', 'pyvenv.cfg'), '');
	mkdirSync(path.join(runtime, 'ros', 'install'), { recursive: true });
	writeFileSync(path.join(runtime, 'ros', 'install', 'setup.bash'), '');
	const bin = path.join(directory, 'bin');
	mkdirSync(bin);
	writeFileSync(path.join(bin, 'uv'), `#!${process.execPath}\nconsole.log(JSON.stringify(process.argv.slice(2)));\n`, { mode: 0o755 });
	const result = spawnSync(process.execPath, [cli, 'sample', 'motor-test', '-D'], {
		cwd: path.resolve(path.dirname(cli), '..'),
		encoding: 'utf8',
		env: { ...process.env, XDG_DATA_HOME: directory, PATH: `${bin}${path.delimiter}${process.env.PATH}` },
	});
	assert.equal(result.status, 0, result.stderr);
	const args = JSON.parse(result.stdout.trim());
	assert.equal(args[0], 'run');
	assert.equal(args.at(-1), path.resolve(path.dirname(cli), '../src/foundation/foundation/samples/odrive_position_test.py'));
	assert.ok(!args.includes('--motor'));
});
