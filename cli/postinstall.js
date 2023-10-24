#! /usr/bin/env node
import fs from 'fs';
import os from 'node:os';
import url from 'url';
/**
 * This is a postinstall script that runs after `npm -g install`.
 * This is a script only for raspberry pi.
 * ** if you have a arm64 linux machine, this will run on your machine. **
 * If you do run this on a local machine, please remove the /opt/catbot/ folder.
 */

// __dirname is not defined in ES6 modules
const __dirname = url.fileURLToPath(new URL('.', import.meta.url));

if (os.arch() !== 'arm64' || os.platform() !== 'linux') {
	console.log('This is not a Linux system. Skipping postinstall.');
	process.exit(0);
}

const CURRENT_SRC_FOLDER = __dirname + '/src';
const OPT_FOLDER = '/opt';
const GLOBAL_CATBOT_FOLDER = '/opt/catbot';
const SRC_FOLDER = '/opt/catbot/src';

// Checking for /opt/ folder
if (!fs.existsSync(OPT_FOLDER)) {
	console.log(`Could not find ${OPT_FOLDER}`);
	console.log(`run 'sudo mkdir ${OPT_FOLDER}'`);
	process.exit(1);
}

// Checking for /opt/catbot/ folder and making it if it doesn't exist
if (!fs.existsSync(GLOBAL_CATBOT_FOLDER)) {
	try {
		fs.mkdirSync(GLOBAL_CATBOT_FOLDER);
		console.log(`New catbot directory made in '${GLOBAL_CATBOT_FOLDER}'.`);
	} catch {
		console.log(
			`Someting went wrong while making new catbot directory at '${GLOBAL_CATBOT_FOLDER}'.`
		);
		process.exit(1);
	}
}

// Checking for /opt/catbot/src/ folder and removing it if it exists
if (fs.existsSync(SRC_FOLDER)) {
	try {
		fs.rmdirSync(SRC_FOLDER, { recursive: true });
		console.log(`Old src directory removed from '${SRC_FOLDER}'.`);
	} catch {
		console.log(
			`Something went wrong while removing old src directory at '${SRC_FOLDER}'.`
		);
		process.exit(1);
	}
}

// Making new /opt/catbot/src/ folder from /main/src/
try {
	fs.cpSync(CURRENT_SRC_FOLDER, GLOBAL_CATBOT_FOLDER, { recursive: true });
} catch {
	console.log(
		`Something went wrong while copying new src directory to '${SRC_FOLDER}'.`
	);
	process.exit(1);
}
console.log('Catbot installed successfully!');
