import { useEffect } from "react";
import { useFormContext, useWatch } from "react-hook-form";
import GenericDetailField from "./GenericDetailField.jsx";
import { Icon } from "./ui";
import { allowedChoices, applies, resolveMetadata, ruleKey } from "../utils/dependentFields";

function Cell({ fieldName, form, value, metadata, errors, modelType, highlighted }) {
    if (!metadata) return null;
    const fieldErr = errors;
    return (
        <div className={`ck-vt-cell ${form ? 'is-form' : ''} ${highlighted ? 'is-ai-filled' : ''}`}>
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
            {form && metadata.help_text && (
                <div className="ck-vt-cell-help">{metadata.help_text}</div>
            )}
            {fieldErr && (
                <div className="ck-vt-cell-error">
                    {Array.isArray(fieldErr) ? fieldErr[0] : (fieldErr.non_field_errors?.[0] || String(fieldErr))}
                </div>
            )}
        </div>
    );
}

// Inside a form, fields follow the values typed so far: a field that stops
// applying is hidden, and a choice that no longer fits is cleared.
function WatchedPane(props) {
    const { control, getValues, setValue } = useFormContext();
    const watched = useWatch({ control });
    const values = { ...props.object, ...getValues(), ...watched };
    const fields = props.metadata || {};
    const choiceRules = Object.entries(fields).filter(([, meta]) => meta?.depends_on?.options_from);
    const choiceKey = choiceRules.map(([name, meta]) => `${name}=${ruleKey(values[name])}|${ruleKey(values[meta.depends_on.options_from])}`).join(",");
    useEffect(() => {
        for (const [name, meta] of choiceRules) {
            const current = ruleKey(values[name]);
            if (current === null || !applies(meta.depends_on, values)) continue;
            const allowed = allowedChoices(meta.depends_on, values);
            if (allowed && !allowed.includes(current)) setValue(name, "", { shouldDirty: true });
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [choiceKey]);
    return <Pane {...props} values={values} />;
}

export default function DetailPane(props) {
    const formContext = useFormContext();
    if (props.form && formContext) return <WatchedPane {...props} />;
    return <Pane {...props} values={props.object || {}} />;
}

function Pane({ field_pairs, form, object, metadata: rawMetadata, errors, modelType, highlighted, values }) {
    const { metadata, hidden } = resolveMetadata(rawMetadata, values);
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
                    // Fields that don't apply to the record as it stands are left out.
                    const row = (Array.isArray(rawRow) ? rawRow : [rawRow]).filter((f) => f && !hidden.has(f));
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
                                    highlighted={highlighted?.has(field)}
                                />
                            ))}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
