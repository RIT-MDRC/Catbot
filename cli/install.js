import ArduinoCli from 'arduino-cli';

const ERROR_MESSAGES = {
	NO_ARDUINO_BOARDS:
		'No arduino boards found\nCheck your connection with the arduino board',
	MULTIPLE_ARDUINO_BOARDS:
		'Multiple arduino boards found\nPlease unplug all but one arduino board\nCheck if there is no similarly named devices connected to the computer',
};

/**
 * @returns {number} exit code
 */
async function install(debug = false) {
	// Get the list of connected boards
	const cli = ArduinoCli.default('arduino-cli', {
		directories: {
			user: './src/arduino',
			data: './src/arduino',
		},
	});
	const boards = await cli.listConnectedBoards();
	try {
		if (debug) console.log(`boards: ${boards}`);
		if (boards.length === 0) {
			console.log(ERROR_MESSAGES.NO_ARDUINO_BOARDS);
			return 1;
		} else if (boards.length > 1) {
			console.log(ERROR_MESSAGES.MULTIPLE_ARDUINO_BOARDS);
			return 1;
		}
		const board = boards[0];
		console.log(`Arduino Board found:`);
		if (debug) console.log(board);
	} catch (err) {
		console.log(`Error getting board information: ${err}`);
		return 1;
	}
	return 0;
}

export { install };
