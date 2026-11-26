// Bookkeeping every record has; without a layout it goes after the record's own fields.
const AUDIT_FIELDS = ["id", "created_at", "created_by", "updated_at", "updated_by"];
const IGNORED_FIELDS = ["deleted", "merged_into"];

function inPairs(fields) {
	const pairs = [];
	for (let i = 0; i < fields.length; i += 2) pairs.push(fields.slice(i, i + 2));
	return pairs;
}

// Fields the person may not see are not in the metadata: a layout that names
// one simply leaves it out.
export default function generateFieldPairs(metadata, layout) {
	const known = (name) => Boolean(metadata.fields[name]);
	const fields = layout?.fields || Object.keys(metadata.fields);

	if (Array.isArray(fields[0])) {
		return fields.map((pair) => pair.filter(known)).filter((pair) => pair.length > 0);
	}

	const shown = fields.filter((name) => !IGNORED_FIELDS.includes(name) && known(name));
	if (layout?.fields) return inPairs(shown);
	return [
		...inPairs(shown.filter((name) => !AUDIT_FIELDS.includes(name))),
		...inPairs(shown.filter((name) => AUDIT_FIELDS.includes(name))),
	];
}
