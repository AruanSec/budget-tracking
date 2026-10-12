import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import ts from 'typescript'

const source = readFileSync(new URL('../src/format.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } })
const { strToCents, evenSplit } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)

test('decimal money input converts exactly to cents', () => {
  for (const [input, expected] of [['0.29', 29], ['1.01', 101], ['12.3', 1230], [' 12. ', 1200], ['0', 0]]) {
    assert.equal(strToCents(input), expected)
  }
})

test('invalid, excess precision and unsafe amounts are rejected', () => {
  for (const input of ['', '12abc', '1.005', '-1', '1e3', 'Infinity', '9007199254740992']) {
    assert.equal(strToCents(input), null, input)
  }
})

test('even split preserves every cent', () => {
  assert.deepEqual(evenSplit(101, 3), [34, 34, 33])
})
