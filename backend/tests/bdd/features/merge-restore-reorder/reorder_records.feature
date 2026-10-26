@endpoint:records.reorder
Feature: Reorder records by dragging them
  On a board sorted by a number field, dragging a card renumbers the cards
  in their new order in one step. Only cards that actually moved are changed,
  and the whole reorder can be undone at once.

  Background:
    Given Alice can view and change topics
    And a topic "Bugs"
    And a topic "Billing"
    And a topic "Sales"

  Scenario: Each record is numbered by its new position
    When Alice reorders the topics by sort order as "Sales", "Bugs" and "Billing"
    Then it succeeds
    And "Sales" has sort order "0"
    And "Bugs" has sort order "1"
    And "Billing" has sort order "2"

  Scenario: Only the records whose position changed are saved
    When Alice reorders the topics by sort order as "Bugs", "Sales" and "Billing"
    Then that change touched only "Sales" and "Billing"

  Scenario: A whole reorder is undone in one step
    Given Alice reordered the topics by sort order as "Sales", "Bugs" and "Billing"
    When Alice undoes that change
    Then it succeeds
    And "Bugs" has sort order "0"
    And "Billing" has sort order "0"

  Scenario: Deleted records are left out of a reorder
    Given Alice can delete topics
    And the sort order of "Billing" is "7"
    And Alice deleted "Billing"
    When Alice reorders the topics by sort order as "Billing", "Sales" and "Bugs"
    Then it succeeds
    And "Billing" still has sort order "7"
    And "Sales" has sort order "1"

  Scenario Outline: Records can only be reordered by a number field they can edit
    When Alice reorders the topics by <field>
    Then it is rejected with "Cannot reorder by"

    Examples:
      | field  |
      | name   |
      | id     |
      | colour |

  Scenario: Only records of the type being reordered can be included
    Given a customer "Acme"
    When Alice reorders the topics by sort order as "Bugs" and "Acme"
    Then it is rejected with "Cannot reorder by"
    And "Bugs" still has sort order "0"
