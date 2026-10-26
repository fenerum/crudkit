@endpoint:records.list
Feature: List records
  Every record type gets a list page. People page through it, narrow it down
  by field values, sort it and pick the columns they need, and only ever see
  the record types they are allowed to view.

  Background:
    Given Alice can view customers

  Scenario: A list is shown page by page with its totals
    Given 3 customers named "Acme" followed by a number
    When Alice lists the customers 2 per page
    Then the list shows 2 of 3 customers, on page 1 of 2
    And the list offers a next page

  Scenario: A later page of the list holds the remaining records
    Given 3 customers named "Acme" followed by a number
    When Alice opens page 2 of the customers, 2 per page
    Then the list shows 1 of 3 customers, on page 2 of 2
    And the list is ordered "Acme 3"
    And the list offers a previous page
    And the list offers no next page

  Scenario: A list holds 50 records per page unless asked otherwise
    When Alice looks at the list of customers
    Then the list holds up to 50 records per page

  Scenario Outline: A page holds at most 1000 records
    When Alice lists the customers <asked> per page
    Then the list holds up to <shown> records per page

    Examples:
      | asked | shown |
      | 10    | 10    |
      | 1000  | 1000  |
      | 5000  | 1000  |

  Scenario: Deleted records are left out of the list
    Given a customer "Acme"
    And a customer "Globex"
    And Alice can delete customers
    And Alice deleted "Globex"
    When Alice looks at the list of customers
    Then the list holds only "Acme"

  Scenario: A list can be narrowed down to one value of a field
    Given a customer "Acme" with status "active"
    And a customer "Initech" with status "churned"
    When Alice lists the customers whose status is "churned"
    Then the list holds only "Initech"

  Scenario: A list can be narrowed down to the records linked to another record
    Given Alice can view topics
    And a topic "Billing"
    And a customer "Acme" with topic "Billing"
    And a customer "Globex"
    When Alice lists the customers whose topic is "Billing"
    Then the list holds only "Acme"

  Scenario: A list can be narrowed down to the person looking at it
    Given Bob is a user without any permissions
    And a customer "Acme" with owner "Alice"
    And a customer "Globex" with owner "Bob"
    When Alice lists the customers whose owner is herself
    Then the list holds only "Acme"

  Scenario Outline: A list can be narrowed down to records with or without a value
    Given a topic "Billing"
    And a customer "Acme" with topic "Billing"
    And a customer "Globex"
    When Alice lists the customers that have <which> topic
    Then the list holds only "<listed>"

    Examples:
      | which | listed |
      | a     | Acme   |
      | no    | Globex |

  Scenario: A list of reminders can be narrowed down to the record they are about
    Given Alice can view reminders
    And a customer "Acme"
    And a customer "Globex"
    And a reminder "Call Acme" with target "Acme"
    And a reminder "Call Globex" with target "Globex"
    When Alice lists the reminders whose target is "Acme"
    Then the list holds only "Call Acme"

  Scenario Outline: Sorting by a name ignores upper and lower case
    Given a customer "beta"
    And a customer "Cobalt"
    And a customer "Alpha"
    When Alice lists the customers sorted by <order>
    Then the list is ordered <listed>

    Examples:
      | order           | listed                          |
      | name            | "Alpha", "beta" and "Cobalt"    |
      | name descending | "Cobalt", "beta" and "Alpha"    |

  Scenario: A list can be sorted by several fields
    Given a customer "Acme" with status "churned"
    And a customer "Globex" with status "active"
    And a customer "Initech" with status "churned"
    When Alice lists the customers sorted by status then name descending
    Then the list is ordered "Globex", "Initech" and "Acme"

  Scenario: A list can show only the chosen fields
    Given a customer "Acme"
    When Alice lists the customers showing only name and status
    Then every row of the list shows only name and status

  @known-bug
  Scenario: Asking for a field the record type does not have is refused, naming the field
    Given a customer "Acme"
    When Alice lists the customers showing only name and colour
    Then it is rejected with "colour"

  Scenario: Listing a record type needs permission to view it
    Given Bob is a user without any permissions
    When Bob looks at the list of customers
    Then it is forbidden

  Scenario: Lists need signing in
    When someone who is not signed in looks at the list of customers
    Then it requires signing in

  Scenario: The record types offered are only those the person may view
    Given Alice can view tickets
    When Alice opens the list of record types
    Then the record types offered include customers and tickets
    And the record types offered leave out topics, comments and reminders
