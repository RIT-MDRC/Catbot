const { exec } = require('child_process');

const HEADER_SECTION = ['Port', 'Protocol', 'Type', 'Board', 'FQBN', 'Core'];

const ERROR_MESSAGES = {
	NO_ARDUINO_BOARDS:
		'No arduino boards found\nCheck your connection with the arduino board',
	MULTIPLE_ARDUINO_BOARDS:
		'Multiple arduino boards found\nPlease unplug all but one arduino board\nCheck if there is no similarly named devices connected to the computer',
};

/**
 * @returns {number} exit code
 */
function install(debug = false) {
	const childProcess = exec('arduino-cli board list');
	childProcess.stdout.on('data', (data) => {
		console.log(data);
		const lines = data.split('\n');
		const header = lines[0];
		let body = lines.slice(1, -2);
		if (!debug) {
			body = body.filter(
				(line) =>
					line.length > 0 && line.toLowerCase().includes('arduino')
			);
			if (body.length === 0) {
				console.log(ERROR_MESSAGES.NO_ARDUINO_BOARDS);
				return 1;
			} else if (body.length > 1) {
				console.log(ERROR_MESSAGES.MULTIPLE_ARDUINO_BOARDS);
				return 1;
			}
		}
		const columnIndices = headerIndices(header);
		const boardInfos = parseBoardInfo(body, columnIndices);
		const board = boardInfos[0];
		console.log(`Arduino Board found:`);
		console.log(board);
		fs.writeFileSync(
			'sketch.yml',
			`default_fqbn: ${board['FQBN']}\n
    default_port: ${board['Port']}\n
    default_protocol: ${board['Protocol']}`
		);
		console.log(boardInfos);
		return 0;
	});
}

function findArduinoBoard(debug) {
	return new Promise((resolve, reject) => {
		let board;
		const childProcess = exec('arduino-cli board list');
		childProcess.stdout.on('data', (data) => {
			console.log(data);
			const lines = data.split('\n');
			const header = lines[0];
			let body = lines.slice(1, -2);
			if (!debug) {
				body = body.filter(
					(line) =>
						line.length > 0 &&
						line.toLowerCase().includes('arduino')
				);
				if (body.length === 0) {
					console.log(ERROR_MESSAGES.NO_ARDUINO_BOARDS);
					return 1;
				} else if (body.length > 1) {
					console.log(ERROR_MESSAGES.MULTIPLE_ARDUINO_BOARDS);
					return 1;
				}
			}
			const columnIndices = headerIndices(header);
			const boardInfos = parseBoardInfo(body, columnIndices);
			board = boardInfos[0];
			console.log(`Arduino Board found:`);
			console.log(board);
		});
	});
}

/**
 *
 * @param {string} header header line from arduino-cli board list
 * @returns {Object<string, number>} header index by header term
 */
function headerIndices(header) {
	const indices = {};
	HEADER_SECTION.forEach((headerTerm) => {
		const index = header.indexOf(headerTerm);
		if (index === -1) {
			throw new Error(`could not find ${headerTerm} in header`);
		}
		indices[headerTerm] = index;
	});
	return indices;
}

/**
 *
 * @param {string[]} lines
 * @param {Object<string, number>} indices
 * @returns {Object<string, string>[]} board info
 */
function parseBoardInfo(lines, indices) {
	const boardInfos = [];
	lines.forEach((currentLine) => {
		const boardInfo = {};
		HEADER_SECTION.forEach((headerTerm, i) => {
			const currentHeaderIndex = indices[headerTerm];
			const nextHeaderTerm = HEADER_SECTION[i + 1];
			const nextHeaderIndex = indices[nextHeaderTerm];
			boardInfo[headerTerm] = currentLine
				.slice(currentHeaderIndex, nextHeaderIndex)
				.trim();
		});
		boardInfos.push(boardInfo);
	});
	return boardInfos;
}

exports.install = install;
