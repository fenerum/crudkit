import GenericDetailField from "./GenericDetailField.jsx";
import { Icon } from "./ui";

function Cell({ fieldName, form, value, metadata, errors, modelType }) {
    if (!metadata) return null;
    const fieldErr = errors;
    return (
        <div className={`ck-vt-cell ${form ? 'is-form' : ''}`}>
            <div className="ck-vt-cell-l">
                {metadata.verbose_name}
                {form && metadata.required && <span className="ck-req">*</span>}
            </div>
            <div className="ck-vt-cell-v">
                <GenericDetailField
                    fieldName={fieldName}
                    value={value}
                    metadata={metadata}
                    form={form}
                    modelType={modelType}
                />
            </div>
            {fieldErr && (
                <div className="ck-vt-cell-error">
                    {Array.isArray(fieldErr) ? fieldErr[0] : (fieldErr.non_field_errors?.[0] || String(fieldErr))}
                </div>
            )}
        </div>
    );
}

export default function DetailPane({ field_pairs, form, object, metadata, errors, modelType }) {
    return (
        <div className="flex flex-col gap-4">
            {form && form.non_field_errors && (
                <div className="flex items-start gap-2.5 rounded-md border border-border-1 bg-bg-2 px-3.5 py-2.5">
                    <span className="text-danger flex-shrink-0 mt-0.5">
                        <Icon name="alert-circle" size={14} color="currentColor" />
                    </span>
                    <div className="flex-1">
                        <h3 className="text-sm font-semibold text-fg-1">
                            There were {form.non_field_errors.length} error(s) with your submission
                        </h3>
                        <ul className="list-disc pl-5 mt-1.5 space-y-1 text-xs text-danger">
                            {Object.entries(form.non_field_errors).map((error) => (
                                <li key={error}>{error}</li>
                            ))}
                        </ul>
                    </div>
                </div>
            )}

            <div className="ck-vt-prop">
                {field_pairs.map((rawRow, rowIdx) => {
                    // A "row" can be a single field name (legacy) or an array of
                    // field names. Normalise + drop empty slots before counting
                    // so a row of just `["text"]` lays out at full width.
                    const row = (Array.isArray(rawRow) ? rawRow : [rawRow]).filter(Boolean);
                    if (row.length === 0) return null;
                    return (
                        <div
                            key={rowIdx}
                            className="ck-vt-cells"
                            style={{ gridTemplateColumns: `repeat(${row.length}, minmax(0, 1fr))` }}
                        >
                            {row.map((field) => (
                                <Cell
                                    key={field}
                                    fieldName={field}
                                    form={form}
                                    value={object?.[field]}
                                    metadata={metadata[field]}
                                    errors={errors?.[field]}
                                    modelType={modelType}
                                />
                            ))}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
