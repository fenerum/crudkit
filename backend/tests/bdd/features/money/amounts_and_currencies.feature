@field:CurrencyField
Feature: Show and convert amounts in a record's currency
  A record with a currency field can show any amount in that currency, with
  the right symbol on the right side, and convert it into another currency
  using the stored exchange rates. The default currency here is DKK.

  Background:
    Given a customer "Acme" with currency "EUR"

  Scenario Outline: An amount in <currency> is shown with its symbol on the usual side
    Given the currency of "Acme" is "<currency>"
    Then "Acme" shows an amount of "1234.5" as "<shown>"

    Examples:
      | currency | shown       |
      | USD      | $1,234.50   |
      | GBP      | £1,234.50   |
      | EUR      | 1,234.50 €  |
      | DKK      | 1,234.50 kr |
      | SEK      | 1,234.50 kr |

  Scenario: An amount can be shown without its symbol
    Then "Acme" shows an amount of "1234.5" without its symbol as "1,234.50"

  Scenario: A missing amount is shown as N/A
    Then "Acme" shows a missing amount as "N/A"

  @known-bug
  Scenario: A record whose own amount is empty shows it as N/A
    Then "Acme" shows its own empty amount as "N/A"

  Scenario: A currency is shown by its name and symbol
    Then the currency of "Acme" reads "Euro" with the symbol "€"

  Scenario: A record's currency defaults to the configured default currency
    Given a customer "Globex"
    Then "Globex" has currency "DKK"

  Scenario: Converting into the same currency leaves the amount as it is
    Then "Acme" converts "1000" into EUR as "1000.00"

  Scenario: Converting at a given rate multiplies by that rate
    Then "Acme" converts "1000" into USD at a rate of "1.2" as "1200.00"

  Scenario: Converting goes through the default currency at the rates of the day
    Given the EUR rate is "0.85" from "2023-01-01" to "2023-12-31"
    And the USD rate is "0.15" from "2023-01-01" onwards
    Then "Acme" converts "1000" into DKK on "2023-06-01" as "1176.47"
    And "Acme" converts "1000" into USD on "2023-06-01" as "176.47"

  Scenario: Converting from the default currency uses the target's rate
    Given the currency of "Acme" is "DKK"
    And the EUR rate is "0.85" from "2023-01-01" to "2023-12-31"
    Then "Acme" converts "1000" into EUR on "2023-06-01" as "850.00"

  Scenario: An amount cannot be converted on a day without a rate
    Given the EUR rate is "0.85" from "2023-01-01" to "2023-12-31"
    And the USD rate is "0.15" from "2023-01-01" onwards
    Then "Acme" cannot convert "1000" into USD on "2024-06-01"

  Scenario: An amount cannot be converted into a currency without a rate
    Given the currency of "Acme" is "DKK"
    Then "Acme" cannot convert "1000" into NOK on "2024-06-01"
