"""Argument checks shared by the public methods of the device families.

These are the contract-level checks: the ones true of every device implementing a
capability, such as a sample count of at least one, or a wavelength inside the
range the instrument itself reports. Limits that vary by model -- the SR830's
+/-10.5 V Aux output, the Millennia's 0.05-25 W -- stay in the driver, next to the
numbers they come from.

Every function raises TypeError for a value of the wrong kind and ValueError for a
value out of bounds, matching what the drivers already raise, and names the
parameter, the offending value and the bound it broke. Each returns the value, so
a caller may write `power = requireAtLeast(power, 0, "power")`.

A capability calls these from the validator it hands to @notifies, which runs them
before the operation is announced: a rejected call never touched the hardware, so
no will/did pair is posted for it.
"""

import numbers


def describeValue(value, unit=None) -> str:
    """Format a value for an error message, with its unit when there is one."""
    return "{0!r} {1}".format(value, unit) if unit else "{0!r}".format(value)


def requireRealNumber(value, name, unit=None):
    """Require a real number: an int or a float, but not a bool and not a string.

    bool is a subclass of int in Python, so True would otherwise pass as the
    number 1 -- a logic level is not a measurement.
    """
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise TypeError("{0} must be a real number, got {1}".format(
            name, describeValue(value, unit)))
    return value


def requireInteger(value, name):
    """Require a whole number, again excluding bool."""
    if isinstance(value, bool) or not isinstance(value, numbers.Integral):
        raise TypeError("{0} must be an integer, got {1!r}".format(name, value))
    return value


def requireBool(value, name):
    """Require a logic level. 0 and 1 are accepted and converted, since a digital
    line is as often written as an int as as a bool; anything else is refused."""
    if isinstance(value, bool):
        return value
    if isinstance(value, numbers.Integral) and value in (0, 1):
        return bool(value)
    raise TypeError(
        "{0} must be True or False (0 and 1 are accepted), got {1!r}".format(name, value))


def requireAtLeast(value, minimum, name, unit=None):
    """Require a real number no smaller than minimum."""
    requireRealNumber(value, name, unit)
    if value < minimum:
        raise ValueError("{0} must be at least {1}, got {2}".format(
            name, describeValue(minimum, unit), describeValue(value, unit)))
    return value


def requirePositive(value, name, unit=None):
    """Require a real number strictly greater than zero."""
    requireRealNumber(value, name, unit)
    if value <= 0:
        raise ValueError("{0} must be greater than zero, got {1}".format(
            name, describeValue(value, unit)))
    return value


def requireWithinRange(value, limits, name, unit=None):
    """Require a real number inside limits, a (low, high) pair, ends included.

    limits of None means the instrument does not report one, and the value passes:
    the check is only as good as what the driver advertises.
    """
    requireRealNumber(value, name, unit)
    if limits is None:
        return value
    low, high = limits
    if not low <= value <= high:
        raise ValueError(
            "{0} must be within [{1}, {2}], got {3}".format(
                name, describeValue(low, unit), describeValue(high, unit),
                describeValue(value, unit)))
    return value


def requireNonEmpty(collection, name):
    """Require a collection with at least one element."""
    if len(collection) == 0:
        raise ValueError("{0} must not be empty".format(name))
    return collection


def requireMember(value, enumeration, name):
    """Require a member of enumeration, accepting anything it can be built from.

    Enum() already raises for an unknown value, but its message names neither the
    parameter nor what was allowed, which is what a user needs to fix the call.
    """
    try:
        return enumeration(value)
    except ValueError:
        raise ValueError("{0} must be one of {1}, got {2!r}".format(
            name, ", ".join(member.name for member in enumeration), value)) from None
