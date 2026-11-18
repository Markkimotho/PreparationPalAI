/**
 * Gate: the web and the phone app share one palette. The vivid and soft shade of every area
 * accent, the brand green and the mint must be identical in mobile/src/constants/theme.ts and
 * frontend/src/styles/theme.css. (Deep shades differ on purpose: the web's are darker for text
 * contrast on white.) The two drifted apart once; this keeps them unified.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { expect, it } from 'vitest';

const root = resolve(__dirname, '../../..');
const mobile = readFileSync(resolve(root, 'mobile/src/constants/theme.ts'), 'utf8');
const web = readFileSync(resolve(root, 'frontend/src/styles/theme.css'), 'utf8');
const lightBlock = mobile.slice(mobile.indexOf('light: {'), mobile.indexOf('dark: {'));

const mobileColour = (key: string) => lightBlock.match(new RegExp(`\\b${key}: '(#[0-9a-f]{6})'`, 'i'))?.[1]?.toLowerCase();
const webColour = (token: string) => web.match(new RegExp(`--${token}:\\s*(#[0-9a-f]{6})`, 'i'))?.[1]?.toLowerCase();

it.each([
  ['blue', 'blue-vivid'], ['blueSoft', 'blue-soft'], ['amber', 'amber-vivid'], ['amberSoft', 'amber-soft'],
  ['green', 'green-vivid'], ['greenSoft', 'green-soft'], ['coral', 'coral-vivid'], ['coralSoft', 'coral-soft'],
  ['brand', 'brand'], ['mint', 'mint'],
])('phone %s equals web --%s', (mobileKey, webToken) => {
  const phone = mobileColour(mobileKey);
  expect(phone, `missing ${mobileKey} in the phone theme`).toBeTruthy();
  expect(webColour(webToken)).toBe(phone);
});
