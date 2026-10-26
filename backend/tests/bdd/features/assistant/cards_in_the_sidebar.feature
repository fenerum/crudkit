@websocket:ws/assistant/ @transactional
Feature: Confirming and skipping the assistant's cards in the sidebar
  The assistant never changes anything itself: each change it proposes shows
  up as a card that the person confirms or skips right in the chat. The
  assistant learns how its cards were resolved with the person's next message.

  Background:
    Given Alice can view and change customers
    And a customer "Acme" with status "active"
    And Alice is looking at "Acme"
    And Alice opened the assistant
    And Alice started a new conversation
    And the assistant will call propose_patch with:
      | set status | churned |
    And Alice asked the assistant "churn this customer"

  Scenario: Confirming a card applies the change without starting a turn
    When Alice confirms the card
    Then the card says "Applied fields: status"
    And "Acme" has status "churned"
    And the assistant does not start a turn

  Scenario: The assistant hears how a card was resolved with the next message, once
    Given Alice confirmed the card
    When Alice asks the assistant "thanks"
    Then the assistant sees "Outcome of proposal"
    And the assistant sees "succeeded. Applied fields: status"
    When Alice asks the assistant "anything else?"
    Then the assistant does not see "Outcome of proposal"

  Scenario: Skipping a card changes nothing, and the assistant hears about it
    When Alice skips the card
    Then the card says "Skipped by user."
    And "Acme" still has status "active"
    When Alice asks the assistant "ok"
    Then the assistant sees "User skipped proposal"

  Scenario: Several cards can be confirmed at once
    Given a customer "Beta" with status "active"
    And the assistant will call propose_bulk_patch with:
      | records    | Acme and Beta |
      | set status | churned       |
    And Alice asked the assistant "churn both"
    When Alice confirms all the cards
    Then every card says "Applied fields: status"
    And "Acme" has status "churned"
    And "Beta" has status "churned"

  Scenario: A card can only be resolved once
    Given Alice confirmed the card
    When Alice confirms the card again
    Then the card says "Already resolved."

  Scenario: A card already resolved in the Inbox says so
    Given the proposal on the card was confirmed in the Inbox
    When Alice skips the card
    Then the card says "Already resolved."
    And "Acme" has status "churned"

  Scenario: A card from another conversation cannot be resolved here
    Given a customer "Beta" with status "active"
    And the assistant proposed in another conversation changing the status of "Beta" to "churned"
    When Alice confirms the card from the other conversation
    Then Alice sees the error "Proposal not found."
    And "Beta" still has status "active"

  Scenario: A card cannot be confirmed by someone who may no longer make the change
    Given Alice may no longer change customers
    When Alice confirms the card
    Then Alice sees the error "Proposal not found."
    And "Acme" still has status "active"
