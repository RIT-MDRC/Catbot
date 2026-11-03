import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
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

test('motor test lets the sample list motors when --motor is omitted', () => {
	const result = spawnSync(process.execPath, [cli, 'sample', 'motor-test', '-D'], {
		cwd: path.resolve(path.dirname(cli), '..'),
		encoding: 'utf8',
	});
	assert.doesNotMatch(result.stderr, /requires --motor/);
});
