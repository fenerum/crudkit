@transactional @field:AISummaryField
Feature: When AI fields are refreshed
  AI fields stay current without anyone asking: saving a record, or adding or
  removing one of its comments, asks the AI again once the change is saved.
  The AI's own update never sets off another round.

  Background:
    Given Alice can view, add, change and delete tickets
    And Alice can view, add, change and delete comments
    And the AI answers:
      | field   | value                        |
      | summary | The customer wants a refund. |

  Scenario: Raising a ticket fills in its AI fields
    When Alice raises a ticket "Refund please"
    Then it succeeds
    And "Refund please" has summary "The customer wants a refund."

  Scenario: The AI's own update does not ask the AI again
    When Alice raises a ticket "Refund please"
    Then the AI was asked about "Refund please" once

  Scenario: Editing a ticket asks the AI about the new content
    Given a ticket "Refund please"
    When Alice changes the subject of "Refund please" to "Refund for order 42"
    Then the AI was asked about "Refund for order 42" once

  Scenario: A new comment refreshes the ticket's AI fields
    Given a ticket "Printer broken"
    When Alice comments "It is on fire now" on "Printer broken"
    Then the AI read the comment "It is on fire now" on "Printer broken"

  Scenario: Removing a comment refreshes the ticket's AI fields
    Given a ticket "Printer broken"
    And a comment "It is on fire now" with ticket "Printer broken"
    When Alice deletes "It is on fire now"
    Then the AI last read "Printer broken" without the comment "It is on fire now"

  Scenario: Saving a record without AI fields does not involve the AI
    Given Alice can view and change customers
    And a customer "Acme"
    When Alice changes the name of "Acme" to "Acme Inc"
    Then the AI was not asked

  Scenario: A save still succeeds when the background worker cannot be reached
    Given the background worker cannot be reached
    When Alice raises a ticket "Refund please"
    Then it succeeds
    And the AI fields of "Refund please" are empty
