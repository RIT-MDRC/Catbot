#! /usr/bin/env node
const yargs = require('yargs');
const { spawn } = require('child_process');
const { install } = require('./install');

yargs
	.command({
		command: 'install',
		aliases: ['i'],
		describe: 'set up arduino and raspberry pi to run catbot',
		handler(args) {
			console.log('installing catbot is still under construction...');
			// return install(args.d);
		},
	})
	.command({
		command: 'start',
		aliases: ['s'],
		describe: 'start catbot',
		builder: (yargs) =>
			yargs.option('f', {
				alias: 'file',
				describe: 'specify file to run',
				default: 'main',
				type: 'string',
			}),
		handler(args) {
			file = args.f ?? args.file ?? 'main';
			console.log(
				`starting catbot${args.f ? ` with file '${args.f}.py'` : '...'}`
			);
			const childProcess = spawn('python', [`src/raspi/${file}.py`], {
				stdio: 'inherit',
			});
			childProcess.on('close', (code) => {
				console.log(`exited with code ${code}`);
			});
		},
	})
	.command({
		command: 'arduino',
		aliases: ['a'],
		describe: 'run arduino cli',
		handler(args) {
			console.log('running arduino cli...');
			const childProcess = spawn('arduino-cli', args._.slice(1), {
				stdio: 'inherit',
			});
			childProcess.on('close', (code) =>
				console.log(`exited with code ${code}`)
			);
		},
	})
	.demandCommand(1, '');

yargs.parse();
