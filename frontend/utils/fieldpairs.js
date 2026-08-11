
export default function generateFieldPairs(metadata, layout) {
	let fieldPairs = Object.keys(metadata.fields);
	if (layout && layout.fields) {
			fieldPairs = layout.fields;
	}

	if (fieldPairs && !Array.isArray(fieldPairs[0])) {
			// This is a single list of fields
			const ignoreFields = ["deleted", "merged_into"];

			fieldPairs = fieldPairs.filter(item => !ignoreFields.includes(item))

			// convert flat list of fields to list of two pairs of fields
			fieldPairs = fieldPairs.reduce((result, value, index, array) => {
					if (index % 2 === 0) {
						result.push(array.slice(index, index + 2));
					}
					return result;
			}, []);
	}
	return fieldPairs;
}