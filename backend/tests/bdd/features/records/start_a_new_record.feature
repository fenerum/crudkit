@endpoint:records.initial @type:LAY
Feature: Start a new record
  A new record's form opens with sensible values: the ones the page it was
  started from passes along, limited to the fields the record type allows.
  A new page layout starts out arranged the way the record's page already
  looks, two fields per row, so people only adjust what they want to change.

  Background:
    Given Alice can view and add customers
    And a topic "Billing"

  Scenario: A new form is prefilled with the values passed along
    When Alice starts a new customer prefilled with name "Acme"
    Then it succeeds
    And the new form is prefilled with name "Acme"
    And the new form leaves email empty

  Scenario: A new form can be prefilled with a linked record
    When Alice starts a new customer prefilled with topic "Billing"
    Then the new form is prefilled with topic "Billing"

  Scenario: A new form only offers the fields the record type allows to be prefilled
    When Alice starts a new customer prefilled with status "churned"
    Then it succeeds
    And the new form does not prefill status

  Scenario: Starting a new record needs permission to add records of its type
    Given Bob can view customers
    When Bob starts a new customer
    Then it is forbidden

  Scenario: A new layout starts with the record's fields two per row
    Given Alice can view and add layouts
    When Alice starts a new layout for customers
    Then the new layout is for customers
    And the new layout places the fields two per row:
      | id         | created_by |
      | created_at | updated_by |
      | updated_at | name       |
      | email      | status     |
      | topic      | owner      |
      | balance    | currency   |

  Scenario: A new layout pairs an odd number of fields with a last row of one
    Given Alice can view and add layouts
    When Alice starts a new layout for topics
    Then the new layout places the fields two per row:
      | id         | created_by |
      | created_at | updated_by |
      | updated_at | name       |
      | sort_order |            |

  Scenario: A saved layout keeps its rows as arranged
    Given Alice can view and add layouts
    When Alice saves a layout for customers with the rows:
      | name  | status |
      | email |        |
    Then it succeeds
    And the layout for customers has the rows:
      | name  | status |
      | email |        |
