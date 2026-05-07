import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

function flattenKeys(value, prefix = "") {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return [prefix];
  }
  return Object.entries(value).flatMap(([key, nested]) => {
    const next = prefix ? `${prefix}.${key}` : key;
    return flattenKeys(nested, next);
  });
}

test("es admin translations include all en admin keys", () => {
  const enPath = resolve(import.meta.dirname, "../messages/en.json");
  const esPath = resolve(import.meta.dirname, "../messages/es.json");
  const en = JSON.parse(readFileSync(enPath, "utf8"));
  const es = JSON.parse(readFileSync(esPath, "utf8"));

  const enKeys = new Set(flattenKeys(en.admin));
  const esKeys = new Set(flattenKeys(es.admin));
  const missing = [...enKeys].filter((key) => !esKeys.has(key));

  assert.deepEqual(missing, []);
});
