import { describe, expect, test } from "vitest";
import { formatNumber, isNumericField } from "../../utils/numbers";

// Formatting follows the runtime locale; the test runner uses en-US.
describe("formatNumber", () => {
  test("groups thousands and keeps the decimals it was given", () => {
    expect(formatNumber("28501.79")).toBe("28,501.79");
    expect(formatNumber("2605.10")).toBe("2,605.10");
    expect(formatNumber("0.00")).toBe("0.00");
  });

  test("shows integers without decimals", () => {
    expect(formatNumber(1234567)).toBe("1,234,567");
    expect(formatNumber(0)).toBe("0");
    expect(formatNumber("-1500")).toBe("-1,500");
  });

  test("leaves anything that is not a number alone", () => {
    expect(formatNumber("n/a")).toBe("n/a");
  });
});

describe("isNumericField", () => {
  test("covers integer, decimal, float and money fields", () => {
    for (const type of ["IntegerField", "PositiveBigIntegerField", "DecimalField", "FloatField", "MoneyField"]) {
      expect(isNumericField({ type })).toBe(true);
    }
  });

  test("excludes text, CK-ID integers and choices", () => {
    expect(isNumericField({ type: "CharField" })).toBe(false);
    expect(isNumericField({ type: "CrudKitPositiveIntegerField" })).toBe(false);
    expect(isNumericField({ type: "IntegerField", choices: [[1, "One"]] })).toBe(false);
    expect(isNumericField(undefined)).toBe(false);
  });
});
