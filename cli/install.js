const { exec } = require('child_process');

const HEADER_SECTION = ['Port', 'Protocol', 'Type', 'Board', 'FQBN', 'Core'];

/**
 * @returns {number} exit code
 */
function install() {
	const childProcess = exec('arduino-cli board list');
	childProcess.stdout.on('data', (data) => {
		console.log(data);
		const lines = data.split('\n');
		const header = lines[0];
		const body = lines
			.slice(1, -2)
			.filter(
				(line) =>
					line.length > 0 && line.toLowerCase().includes('arduino')
			);
		if (body.length === 0) {
			console.log('No arduino boards found');
			return 1;
		}
		const columnIndices = headerIndices(header);
		const boardInfos = parseBoardInfo(body, columnIndices);
		console.log(boardInfos);
		return 0;
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
