@type:VIW
Feature: Count a view in the menu
  A view can show a badge in the menu with how many records it holds, such
  as open tickets waiting for someone. Badge filters narrow the count further
  than the view itself, for example to only the records of the person looking.

  Background:
    Given Alice can view views
    And Alice can view customers
    And Bob can view views
    And Bob can view customers
    And a customer "Acme" with:
      | status | active |
      | owner  | Alice  |
    And a customer "Globex" with:
      | status | churned |
      | owner  | Alice   |
    And a customer "Initech" with:
      | status | active |
      | owner  | Bob    |

  Scenario: Without badge filters the badge counts what the view shows
    Given Alice saved a view "Active" of customers with:
      | filter        | status = active |
      | badge in menu | yes             |
    Then the menu badge of "Active" shows 2 for Alice

  Scenario: Badge filters count only part of what the view shows
    Given Alice saved a view "Active" of customers with:
      | filter        | status = active |
      | badge filter  | owner = ${user} |
      | badge in menu | yes             |
    When Alice opens the view "Active"
    Then the view shows "Acme" and "Initech"
    And the menu badge of "Active" shows 1 for Alice
    And the menu badge of "Active" shows 1 for Bob

  Scenario: Deleted records are not counted in the badge
    Given Alice saved a view "Active" of customers with:
      | filter        | status = active |
      | badge in menu | yes             |
    And "Initech" has since been deleted
    Then the menu badge of "Active" shows 1 for Alice
