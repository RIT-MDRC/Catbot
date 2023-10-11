import { spawn } from 'child_process';

function upload() {
	console.log('uploading catbot code to arduino...');
	const childProcess = spawn('arduino-cli', ['compile', './src/arduino'], {
		stdio: 'inherit',
	});
	childProcess.on('close', (code) => {
		console.log(`compile exited with code ${code}`);
		if (code !== 0) {
			console.error('compile failed');
			return;
		}
		// upload
		const childProcess2 = spawn(
			'arduino-cli',
			['upload', '../src/arduino'],
			{
				stdio: 'inherit',
			}
		);
		childProcess2.on('close', (code) => {
			console.log(`upload exited with code ${code}`);
			if (code !== 0) {
				console.error('upload failed');
				return;
			}
			console.log('upload complete');
		});
	});
}

export { upload };
