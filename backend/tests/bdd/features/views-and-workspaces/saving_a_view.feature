@type:VIW
Feature: Save a view
  A saved view is a named way of looking at one record type: which columns
  it shows, how it filters, sorts, groups and totals, and how it is laid out.
  A view is checked when it is saved, so a typo in a field name or a filter
  is caught at once instead of breaking the list for everyone later.

  Background:
    Given Alice can view, add, change and delete views
    And Alice can view customers

  Scenario: A view is saved with everything it was given
    When Alice saves a view "Big accounts" of customers with:
      | fields         | name, status, balance |
      | filter         | status = active      |
      | order by       | -balance             |
      | layout         | kanban               |
      | group by       | status               |
      | aggregate by   | balance              |
      | aggregate type | sum                  |
    Then it succeeds
    And "Big accounts" has layout "kanban"
    And "Big accounts" has order by "-balance"
    And "Big accounts" has aggregate type "sum"

  Scenario: Every filter comparator is accepted
    When Alice saves a view "Ranges" of customers with:
      | filter  | balance = 1  |
      | filter  | balance != 2 |
      | filter  | balance > 0  |
      | filter  | balance >= 1 |
      | filter  | balance < 9  |
      | filter  | balance <= 9 |
    Then it succeeds

  Scenario: A view for a record type that does not exist is refused
    When Alice saves a view "Nowhere" for a record type that does not exist
    Then it is rejected with "Model 'ZZZ' does not exist."
    And there is no saved view "Nowhere"

  Scenario Outline: A view is refused when <problem>
    When Alice saves a view "Broken" of customers with:
      | <setting> | <value> |
    Then it is rejected with "<message>"
    And there is no saved view "Broken"

    Examples:
      | problem                                         | setting        | value            | message                                            |
      | it shows a field the type does not have         | fields         | name, nickname   | Field 'nickname' does not exist                    |
      | a filter is missing its value                   | filter         | status =         | Filter format is invalid                           |
      | a filter names a field the type does not have   | filter         | nickname = Bob   | Field 'nickname' does not exist                    |
      | a filter compares in an unknown way             | filter         | status ~ churned | Unknown comparator '~'                             |
      | a badge filter compares in an unknown way       | badge filter   | status ~ churned | Unknown comparator '~'                             |
      | a badge filter names a field it does not have   | badge filter   | nickname = Bob   | Field 'nickname' does not exist                    |
      | it sorts by a field the type does not have      | order by       | name,-nickname   | Field 'nickname' does not exist                    |
      | it groups by a field the type does not have     | group by       | nickname         | Field 'nickname' does not exist                    |
      | it pivots by a field the type does not have     | pivot by       | nickname         | Field 'nickname' does not exist                    |
      | it totals a field the type does not have        | aggregate by   | nickname         | Field 'nickname' does not exist                    |
      | it totals a field without saying how            | aggregate by   | balance          | Aggregate type must be set                         |
      | it says how to total without naming a field     | aggregate type | sum              | Aggregate type should not be set                   |
      | it is a quadrant with fewer than two fields     | layout         | quadrant         | Quadrant views require at least 2 fields           |

  Scenario: A filter on a field of a linked record is not checked when saving
    When Alice saves a view "Billing topics" of customers with:
      | filter  | topic__name = Billing |
    Then it succeeds

  Scenario: A quadrant view with two fields is accepted
    When Alice saves a view "Value vs status" of customers with:
      | layout  | quadrant        |
      | fields  | balance, status |
    Then it succeeds
