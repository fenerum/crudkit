import { describe, expect, test } from "vitest";
import { allowedChoices, applies, matchFilter, resolveMetadata, ruleKey } from "../../utils/dependentFields";

const metadata = {
  stage: { type: "CharField", choices: [["open", "Open"], ["lost", "Lost"]], depends_on: null },
  lost_reason: { type: "CharField", required: false, depends_on: { when: { stage: ["lost"] }, required: true } },
  special_terms: { type: "TextField", depends_on: { when: { has_special_terms: ["true"] } } },
  product: {
    type: "CharField",
    choices: [["laptop", "Laptop"], ["phone", "Phone"], ["saas", "Saas"]],
    depends_on: { options_from: "category", options: { hardware: ["laptop", "phone"] } },
  },
  ticket: { type: "ForeignKey", depends_on: { match: { customer: "customer" } } },
};

describe("dependent fields", () => {
  test("compares records by ID and yes/no as true/false", () => {
    expect(ruleKey({ id: "CUS1", label: "Acme" })).toBe("CUS1");
    expect(ruleKey(true)).toBe("true");
    expect(ruleKey("")).toBeNull();
    expect(ruleKey(3)).toBe("3");
  });

  test("a field applies only while its conditions hold", () => {
    const rule = metadata.lost_reason.depends_on;
    expect(applies(rule, { stage: "lost" })).toBe(true);
    expect(applies(rule, { stage: "open" })).toBe(false);
    expect(applies(null, {})).toBe(true);
  });

  test("hides fields that don't apply and requires those that must be filled in", () => {
    const open = resolveMetadata(metadata, { stage: "open", has_special_terms: false });
    expect([...open.hidden].sort()).toEqual(["lost_reason", "special_terms"]);
    const lost = resolveMetadata(metadata, { stage: "lost", has_special_terms: true });
    expect(lost.hidden.size).toBe(0);
    expect(lost.metadata.lost_reason?.required).toBe(true);
  });

  test("narrows choices to those that fit the other field", () => {
    expect(allowedChoices(metadata.product.depends_on, { category: "hardware" })).toEqual(["laptop", "phone"]);
    expect(allowedChoices(metadata.product.depends_on, { category: "" })).toBeNull();
    expect(allowedChoices(metadata.product.depends_on, { category: "software" })).toBeNull();
    const { metadata: resolved } = resolveMetadata(metadata, { category: "hardware" });
    expect(resolved.product?.choices?.map(([v]: [string, string]) => v)).toEqual(["laptop", "phone"]);
  });

  test("filters linked-record pickers by the record's own value", () => {
    expect(matchFilter(metadata.ticket.depends_on, { customer: { id: "CUS1", label: "Acme" } })).toEqual({ customer: "CUS1" });
    expect(matchFilter(metadata.ticket.depends_on, { customer: null })).toBeNull();
  });
});
