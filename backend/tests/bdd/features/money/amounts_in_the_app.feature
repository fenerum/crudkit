@field:MoneyField
Feature: Amounts in the app
  An amount field is shown together with its currency and, when that is not
  the default currency, what it is worth in the default currency, so lists
  of mixed currencies can still be compared. Amounts are entered as plain
  numbers and kept to two decimal places.

  Background:
    Given Alice can view and change customers
    And the EUR rate is "0.134" from "2000-01-01" onwards
    And a customer "Acme" with:
      | currency | EUR  |
      | balance  | 1000 |

  Scenario: An amount is shown with its currency and its worth in the default currency
    When Alice looks at "Acme"
    Then the balance reads "1000.00" EUR, which is "7462.69" DKK

  Scenario: An amount in the default currency is worth the same
    Given the currency of "Acme" is "DKK"
    When Alice looks at "Acme"
    Then the balance reads "1000.00" DKK, which is "1000.00" DKK

  @known-bug
  Scenario: Without an exchange rate, an amount's worth in the default currency is unknown
    Given a customer "Globex" with:
      | currency | USD |
      | balance  | 250 |
    When Alice looks at "Globex"
    Then the balance reads "250.00" USD, with no known worth in DKK

  Scenario: A missing amount is shown as nothing
    Given a customer "Globex"
    When Alice looks at "Globex"
    Then the balance reads nothing

  Scenario: Each record in a list shows its amount in its own currency
    Given a customer "Globex" with:
      | currency | DKK |
      | balance  | 250 |
    When Alice lists the customers with their balances
    Then the balance of "Acme" in the list reads "1000.00" EUR, which is "7462.69" DKK
    And the balance of "Globex" in the list reads "250.00" DKK, which is "250.00" DKK

  Scenario: An amount can be entered as a plain number
    When Alice changes the balance of "Acme" to "12.5"
    Then it succeeds
    And "Acme" has balance "12.50"

  Scenario: An amount can be entered as an amount
    When Alice changes the balance of "Acme" to an amount of "12.5"
    Then it succeeds
    And "Acme" has balance "12.50"

  Scenario: Amounts are kept to two decimal places
    When Alice changes the balance of "Acme" to "12.3456"
    Then it succeeds
    And "Acme" has balance "12.35"

  Scenario: Something that is not a number is refused as an amount
    When Alice changes the balance of "Acme" to "lots"
    Then it is rejected with "Invalid decimal value"
    And "Acme" still has balance "1000.00"

  Scenario: An amount that is not a number is refused
    When Alice changes the balance of "Acme" to an amount of "lots"
    Then it is rejected with "Invalid decimal value for amount"
