@type:EXR
Feature: Exchange rates
  An exchange rate says how much of a currency one unit of the default
  currency (DKK) buys, from a start date until an end date or indefinitely.
  For each currency and day exactly one rate applies, so overlapping periods
  are refused.

  Background:
    Given Alice is a superuser
    And the EUR rate is "0.85" from "2023-01-01" to "2023-12-31"

  Scenario: The rate of a day is the one whose period covers it
    Then the EUR rate on "2023-06-01" is "0.85"
    And the EUR rate on "2023-12-31" is "0.85"
    And there is no EUR rate on "2024-01-01"

  Scenario: A rate without an end applies from its start onwards
    Given the USD rate is "0.15" from "2023-01-01" onwards
    Then the USD rate on "2030-01-01" is "0.15"
    And there is no USD rate on "2022-12-31"

  Scenario: The default currency is always worth exactly 1
    Then the DKK rate on "1999-01-01" is "1"

  Scenario: When overlapping rates exist anyway, the latest start wins
    Given overlapping USD rates were stored directly:
      | from       | to      | rate |
      | 2023-01-01 | onwards | 0.15 |
      | 2023-06-01 | onwards | 0.16 |
    Then the USD rate on "2023-07-01" is "0.16"

  Scenario: A rate is labelled with the base currency and the period it covers
    When Alice looks at that EUR rate
    Then that rate is labelled "1 DKK = 0.85000000 EUR (2023-01-01 - 2023-12-31)"

  Scenario: A rate without an end is labelled as ongoing
    Given the USD rate is "0.15" from "2023-01-01" onwards
    When Alice looks at that USD rate
    Then that rate is labelled "1 DKK = 0.15000000 USD (2023-01-01 - ongoing)"

  Scenario Outline: A new rate may not overlap an existing one for the same currency
    When Alice adds an EUR rate of "0.9" from "<from>" <until>
    Then it is rejected with "overlaps with an existing rate"
    And there is 1 EUR rate

    Examples:
      | from       | until            |
      | 2023-06-01 | to "2023-12-31"  |
      | 2022-06-01 | to "2023-01-01"  |
      | 2022-01-01 | onwards          |
      | 2023-12-31 | onwards          |

  Scenario Outline: A new rate next to an existing one is accepted
    When Alice adds an EUR rate of "0.9" from "<from>" <until>
    Then it succeeds
    And there are 2 EUR rates

    Examples:
      | from       | until           |
      | 2024-01-01 | onwards         |
      | 2022-01-01 | to "2022-12-31" |

  Scenario: Rates for different currencies do not overlap each other
    When Alice adds a USD rate of "0.15" from "2023-01-01" onwards
    Then it succeeds

  Scenario: A rate that ends before it starts is refused
    When Alice adds a USD rate of "0.15" from "2023-12-31" to "2023-01-01"
    Then it is rejected with "End date must be after start date"
    And there is no USD rate

  Scenario: The database itself refuses a rate that ends before it starts
    When a USD rate ending before it starts is stored directly
    Then the database refuses it

  Scenario: Changing a rate does not count as overlapping itself
    When Alice changes that EUR rate to "0.86"
    Then it succeeds
    And the EUR rate on "2023-06-01" is "0.86"
