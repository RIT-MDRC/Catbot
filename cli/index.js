#! /usr/bin/env node
const yargs = require('yargs');
const { spawn } = require('child_process');
const { install } = require('./install');

yargs
	.command({
		command: 'install',
		aliases: ['i'],
		describe: 'set up arduino and raspberry pi to run catbot',
		handler() {
			console.log('installing catbot...');
			return install();
		},
	})
	.command({
		command: 'start',
		aliases: ['s'],
		describe: 'start catbot',
		handler() {
			console.log('starting catbot...');
			const childProcess = spawn('python', ['src/raspi/main.py'], {
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
