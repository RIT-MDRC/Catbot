#! /usr/bin/env node
const yargs = require('yargs');
const { spawn } = require('child_process');

yargs
	.command({
		command: 'install',
		aliases: ['i'],
		describe: 'set up arduino and raspberry pi to run catbot',
		handler() {
			console.log('installing catbot...');
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
				console.log(`child process exited with code ${code}`);
			});
		},
	})
	.demandCommand(1, '');

yargs.parse();
