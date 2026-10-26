@type:EXR
Feature: Manage exchange rates from the command line
  Operators can seed a fresh installation with approximate default rates and
  set a currency's rate for a period from the command line, for example from
  a scheduled job. Rates set this way are recorded as made by the system.

  @command:add_default_exchange_rates
  Scenario: Default rates are added for every other currency from today, with no end
    When an operator runs "add_default_exchange_rates"
    Then the command reports "All default exchange rates added successfully!"
    And there are rates from today with no end for EUR, GBP, NOK, SEK and USD
    And there is an EUR rate of "0.134" from today with no end
    And there is no DKK rate

  @command:add_default_exchange_rates
  Scenario: A currency that already has an open-ended rate keeps it
    Given the EUR rate is "0.2" from "2020-01-01" onwards
    When an operator runs "add_default_exchange_rates"
    Then the command reports "Exchange rate for EUR already exists"
    And there is 1 EUR rate
    And the EUR rate on "today" is "0.2"

  @command:add_default_exchange_rates
  Scenario: A rate that has ended does not stop a default rate being added
    Given the EUR rate is "0.2" from "2020-01-01" to "2020-12-31"
    When an operator runs "add_default_exchange_rates"
    Then there are 2 EUR rates
    And the EUR rate on "today" is "0.134"

  @command:add_default_exchange_rates
  Scenario: Adding the default rates twice adds nothing the second time
    Given an operator ran "add_default_exchange_rates"
    When an operator runs "add_default_exchange_rates"
    Then the command reports "Exchange rate for USD already exists"
    And there is 1 USD rate

  @command:set_exchange_rate
  Scenario: Setting a rate starts it today with no end, as the system
    When an operator runs "set_exchange_rate EUR 0.13425"
    Then the command reports "Created exchange rate: 1 DKK = 0.13425 EUR"
    And there is an EUR rate of "0.13425" from today with no end, set by the system

  @command:set_exchange_rate
  Scenario: A rate can be set for a given period
    When an operator runs "set_exchange_rate EUR 0.13 --from-date 2024-01-01 --to-date 2024-12-31"
    Then the command reports "(from 2024-01-01 to 2024-12-31)"
    And there is an EUR rate of "0.13" from "2024-01-01" to "2024-12-31"

  @command:set_exchange_rate
  Scenario: The currency may be given in lower case
    When an operator runs "set_exchange_rate usd 0.15"
    Then there is a USD rate of "0.15" from today with no end

  @command:set_exchange_rate
  Scenario: Setting a rate that already exists for the period only warns
    Given an operator ran "set_exchange_rate EUR 0.13 --from-date 2024-01-01"
    When an operator runs "set_exchange_rate EUR 0.14 --from-date 2024-01-01"
    Then the command reports "Use --update to modify it."
    And the EUR rate on "2024-06-01" is "0.13"

  @command:set_exchange_rate
  Scenario: An existing rate for the period can be updated
    Given an operator ran "set_exchange_rate EUR 0.13 --from-date 2024-01-01"
    When an operator runs "set_exchange_rate EUR 0.14 --from-date 2024-01-01 --update"
    Then the command reports "Updated exchange rate: 1 DKK = 0.14 EUR"
    And the EUR rate on "2024-06-01" is "0.14"
    And there is 1 EUR rate

  @command:set_exchange_rate
  Scenario Outline: Dates must be written as year-month-day
    When an operator runs "set_exchange_rate EUR 0.13 <option> 01/01/2024"
    Then the command fails with "<message>"
    And there is no EUR rate

    Examples:
      | option      | message                                   |
      | --from-date | Invalid from-date format. Use YYYY-MM-DD. |
      | --to-date   | Invalid to-date format. Use YYYY-MM-DD.   |

  @command:set_exchange_rate
  Scenario: A period may not end before it starts
    When an operator runs "set_exchange_rate EUR 0.13 --from-date 2024-06-01 --to-date 2024-01-01"
    Then the command fails with "End date must be after start date."
    And there is no EUR rate

  @command:set_exchange_rate
  Scenario: A rate overlapping an existing one is refused
    Given an operator ran "set_exchange_rate EUR 0.13 --from-date 2024-01-01"
    When an operator runs "set_exchange_rate EUR 0.14 --from-date 2024-06-01"
    Then the command fails with "overlaps with an existing rate"
    And there is 1 EUR rate
    And the EUR rate on "2024-06-01" is "0.13"

  @command:set_exchange_rate
  Scenario: A rate that is not a number is refused
    When an operator runs "set_exchange_rate EUR lots"
    Then the command fails with "Invalid rate"
    And there is no EUR rate
