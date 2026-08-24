export const list = new RegExp("([A-Z]{3})");
export const detail = new RegExp("([A-Z]{3}\\d+)");

export const capitalize = (str: string): string => {
  if (!str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1);
};

export const url = (
    obj: string, action: string = null, queryParams: Record<string, any> = {},
    view: string = ""
): string => {
    let returnURL: string = "";

    if (detail.test(obj)) {
        const objectUrl = `/${obj}`;
        if (action === 'edit') {
            returnURL = `${objectUrl}/edit`;
        } else if (action === 'delete') {
            returnURL = `${objectUrl}/delete`;
        } else if (action !== null) {
            throw Error(`Invalid action: ${action}`);
        } else {
            returnURL = objectUrl;
        }
    } else if (list.test(obj)) {
        returnURL = `/${obj}/`;
        if (action === 'create') {
            returnURL += `create`;
        } else if (action === 'merge') {
            returnURL += `merge`;
        } else if (action !== null) {
            throw Error(`Invalid action: ${action}`);
        } else if (view !== "") {
            returnURL += "VIW/" + view;
        }
    } else {
        throw Error(`Invalid object name: ${obj}`);
    }
    const qs = queryParams ? new URLSearchParams(queryParams).toString() : "";
    return qs ? `${returnURL}?${qs}` : returnURL;
}

export const valid_url = (obj: string, action: string = null): boolean => {
    try {
        url(obj, action);
        return true;
    } catch {
        return false;
    }
}