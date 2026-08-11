import { Link } from "react-router-dom";
import React, { useState } from "react";

// ActionButton component with optional ref forwarding
function ActionButton({ url, text, color = "gray", onPress, buttonRef }) {
    const [isProcessing, setIsProcessing] = useState(false);

    const getWebClassName = () => {
        const variant =
            color === "red"    ? "ck-btn-danger" :
            color === "green"  ? "ck-btn-success" :
            color === "indigo" ? "ck-btn-primary" :
                                  "ck-btn-secondary";
        return `ck-btn ${variant} ${isProcessing ? 'opacity-70 cursor-not-allowed' : ''}`.trim();
    };

    const handlePress = () => {
        if (isProcessing || !onPress) return;

        setIsProcessing(true);

        try {
            const result = onPress();

            if (result instanceof Promise) {
                result
                    .catch(error => {
                        console.error("Action error:", error);
                    })
                    .finally(() => {
                        setIsProcessing(false);
                    });
            } else {
                setTimeout(() => {
                    setIsProcessing(false);
                }, 500);
            }
        } catch (error) {
            console.error("Action execution error:", error);
            setIsProcessing(false);
        }
    };

    if (onPress) {
        return (
            <button
                type="button"
                onClick={handlePress}
                className={getWebClassName()}
                disabled={isProcessing}
            >
                <span className="flex items-center justify-center">
                    {isProcessing && (
                        <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                    )}
                    {text}
                </span>
            </button>
        );
    }

    return (
        <Link to={url} className={getWebClassName()} ref={buttonRef}>
            <span className="flex items-center justify-center">
                {text}
            </span>
        </Link>
    );
}

export default ActionButton;
