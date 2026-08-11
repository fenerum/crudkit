import * as React from "react";
import BaseField, { BaseFieldProps } from "./BaseField";
import BaseWYSIWYGEditor from "./BaseWYSIWYGEditor";

interface WYSIWYGEditorFieldProps extends BaseFieldProps {
  modelType?: string;
}

export default function WYSIWYGEditorField({
  fieldName,
  defaultValue = "",
  metadata,
  modelType,
  ...rest
}: WYSIWYGEditorFieldProps) {
  return (
    <BaseField
      fieldName={fieldName}
      defaultValue={defaultValue}
      metadata={metadata}
      {...rest}
    >
      {({ value, onChange, onBlur, hasError, ref }) => (
        <BaseWYSIWYGEditor
          value={value}
          onChange={onChange}
          onBlur={onBlur}
          hasError={hasError}
          modelType={modelType}
        />
      )}
    </BaseField>
  );
}
