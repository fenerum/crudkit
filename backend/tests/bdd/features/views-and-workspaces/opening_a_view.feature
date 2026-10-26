@type:VIW
Feature: Open a saved view
  Opening a saved view lists the records it filters for, in its own order,
  with grouped and pivoted views keeping their groups together. A filter can
  refer to "${user}", the person looking, so one shared view such as "My
  customers" shows each person their own records.

  Background:
    Given Alice can view views
    And Alice can view customers
    And Bob can view views
    And Bob can view customers
    And a topic "Billing"
    And a topic "Support"
    And a customer "Acme" with:
      | status  | active |
      | balance | 10     |
      | topic   | Billing |
      | owner   | Alice  |
    And a customer "Globex" with:
      | status  | churned |
      | balance | 50      |
      | topic   | Billing |
      | owner   | Bob     |
    And a customer "Initech" with:
      | status  | active  |
      | balance | 30      |
      | topic   | Support |
      | owner   | Bob     |

  Scenario Outline: A view filtering with "<comparator>" shows the matching records
    Given Alice saved a view "Filtered" of customers with:
      | filter  | balance <comparator> <amount> |
    When Alice opens the view "Filtered"
    Then the view shows <shown>

    Examples:
      | comparator | amount | shown                   |
      | =          | 10     | "Acme"                  |
      | !=         | 10     | "Globex" and "Initech"  |
      | >          | 10     | "Globex" and "Initech"  |
      | >=         | 30     | "Globex" and "Initech"  |
      | <          | 30     | "Acme"                  |
      | <=         | 30     | "Acme" and "Initech"    |

  Scenario: Every filter of a view must match
    Given Alice saved a view "Active and big" of customers with:
      | filter  | status = active |
      | filter  | balance > 10    |
    When Alice opens the view "Active and big"
    Then the view shows "Initech"

  Scenario: A view can filter on a linked record
    Given Alice saved a view "Billing" of customers with:
      | filter  | topic = Billing |
    When Alice opens the view "Billing"
    Then the view shows "Acme" and "Globex"

  Scenario: A view can filter on a field of a linked record
    Given Alice saved a view "Support" of customers with:
      | filter  | topic__name = Support |
    When Alice opens the view "Support"
    Then the view shows "Initech"

  Scenario: A view filtering on the person looking shows each person their own records
    Given Alice saved a view "My customers" of customers with:
      | filter  | owner = ${user} |
    When Alice opens the view "My customers"
    Then the view shows "Acme"
    When Bob opens the view "My customers"
    Then the view shows "Globex" and "Initech"

  Scenario: Deleted records never show in a view
    Given Alice saved a view "Everyone" of customers
    And "Globex" has since been deleted
    When Alice opens the view "Everyone"
    Then the view shows "Acme" and "Initech"

  Scenario: A view lists records in its own order
    Given Alice saved a view "Biggest first" of customers with:
      | order by | -balance |
    When Alice opens the view "Biggest first"
    Then the view shows "Globex", "Initech" and "Acme" in that order

  Scenario: Sorting a view by hand replaces its own order
    Given Alice saved a view "Biggest first" of customers with:
      | order by | -balance |
    When Alice opens the view "Biggest first" sorted by "name"
    Then the view shows "Acme", "Globex" and "Initech" in that order

  Scenario: Names sort the same whatever their capitals
    Given a customer "beta"
    And Alice saved a view "By name" of customers with:
      | order by | name  |
    When Alice opens the view "By name"
    Then the view shows "Acme", "beta", "Globex" and "Initech" in that order

  Scenario: A grouped view keeps each group together, then sorts within it
    Given Alice saved a view "By status" of customers with:
      | group by | status |
      | order by | -name  |
    When Alice opens the view "By status"
    Then the view shows "Initech", "Acme" and "Globex" in that order

  Scenario: A grouped view sorted by hand still keeps its groups together
    Given Alice saved a view "By status" of customers with:
      | group by | status |
    When Alice opens the view "By status" sorted by "-balance"
    Then the view shows "Initech", "Acme" and "Globex" in that order

  Scenario: A pivoted view groups by its pivot before its grouping
    Given Alice saved a view "Status by topic" of customers with:
      | pivot by | status |
      | group by | topic  |
    When Alice opens the view "Status by topic"
    Then the view shows "Acme", "Initech" and "Globex" in that order

  Scenario: Opening a view that does not exist is not found
    When Alice opens a view that does not exist
    Then the view is not found

  Scenario: Opening someone else's private view is not found
    Given Alice saved a private view "Alice's list" of customers
    When Bob opens the view "Alice's list"
    Then the view is not found

  Scenario: A view cannot be opened on a list of another record type
    Given Alice can view tickets
    And Alice saved a view "Everyone" of customers
    When Alice opens the view "Everyone" on the ticket list
    Then it is rejected with "Saved view does not match this model."
