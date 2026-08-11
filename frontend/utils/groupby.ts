export const groupBy = (array, getter, ret=(val) => val) => {
  return array.reduce((result, currentValue) => {
    const groupKey = getter(currentValue);

    if (!result[groupKey]) {
      result[groupKey] = [];
    }

    result[groupKey].push(ret(currentValue));

    return result;
  }, {});
};
