import re

from . import ZipCodeRuleInclusionType


def group_values(pattern, *values):
    result = []
    for value in values:
        try:
            val = re.match(pattern, value)
        except TypeError:
            result.append(None)
        else:
            result.append(val.groups() if val else None)
    return result


def cast_tuple_index_to_type(index, target_type, *tuples):
    """Cast tuple index to type.

    Return list of tuples same as received but with index item casted to
    tagret_type.
    """
    result = []
    for _tuple in tuples:
        to_result = []
        try:
            for i, entry in enumerate(_tuple):
                to_result.append(entry if i != index else target_type(entry))
        except TypeError:
            pass
        result.append(tuple(to_result))
    return result


def compare_values(code, start, end):
    if not code or not start:
        return False
    if not end:
        return start <= code
    return start <= code <= end


def check_uk_zip_code(code, start, end):
    """Check zip code for uk, split the code by regex.

    Example zip codes: BH20 2BC  (UK), IM16 7HF  (Isle of Man).
    """
    pattern = r"^([A-Z]{1,2})([0-9]+)([A-Z]?) ?([0-9][A-Z]{2})$"
    code, start, end = group_values(pattern, code, start, end)
    # replace second item of each tuple with it's value casted to int
    code, start, end = cast_tuple_index_to_type(1, int, code, start, end)
    return compare_values(code, start, end)


def check_irish_zip_code(code, start, end):
    """Check zip code for Ireland, split the code by regex.

    Example zip codes: A65 2F0A, A61 2F0G.
    """
    pattern = r"([\dA-Z]{3}) ?([\dA-Z]{4})"
    code, start, end = group_values(pattern, code, start, end)
    return compare_values(code, start, end)


def check_any_zip_code(code, start, end):
    """Fallback for any country not present in country_func_map.

    Perform simple lexicographical comparison without splitting to sections.
    """
    return compare_values(code, start, end)


def check_zip_code_in_range(country, code, start, end):
    country_func_map = {
        "GB": check_uk_zip_code,  # United Kingdom
        "IM": check_uk_zip_code,  # Isle of Man
        "GG": check_uk_zip_code,  # Guernsey
        "JE": check_uk_zip_code,  # Jersey
        "IE": check_irish_zip_code,  # Ireland
    }
    return country_func_map.get(country, check_any_zip_code)(code, start, end)


def check_shipping_method_for_zip_code(customer_shipping_address, method):
    country = customer_shipping_address.country.code
    postal_code = customer_shipping_address.postal_code
    zip_code_rules = method.zip_code_rules.all()
    if not zip_code_rules:
        return {}
    results = {}
    for zip_code_rule in zip_code_rules:
        results[zip_code_rule] = check_zip_code_in_range(
            country, postal_code, zip_code_rule.start, zip_code_rule.end
        )
    return results


def is_shipping_method_applicable_for_zip_code(
    customer_shipping_address, method
) -> bool:
    """Return if shipping method is applicable with the ZIP code rules."""
    results = check_shipping_method_for_zip_code(customer_shipping_address, method)
    if not results:
        return True
    if all(
        map(
            lambda rule: rule.inclusion_type == ZipCodeRuleInclusionType.INCLUDE,
            results.keys(),
        )
    ):
        return any(results.values())
    if all(
        map(
            lambda rule: rule.inclusion_type == ZipCodeRuleInclusionType.EXCLUDE,
            results.keys(),
        )
    ):
        return not any(results.values())
    # Shipping methods with complex rules are not supported for now
    return False


def filter_shipping_methods_by_zip_code_rules(shipping_methods, shipping_address):
    """Filter shipping methods for given address by ZIP code rules."""

    excluded_methods_by_zip_code = []
    for method in shipping_methods:
        if not is_shipping_method_applicable_for_zip_code(shipping_address, method):
            excluded_methods_by_zip_code.append(method.pk)
    if excluded_methods_by_zip_code:
        return shipping_methods.exclude(pk__in=excluded_methods_by_zip_code)
    return shipping_methods
