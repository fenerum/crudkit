@websocket:ws/assistant/ @transactional
Feature: Taking turns with the assistant
  When a person sends a message, the assistant answers in one turn. The
  sidebar shows the turn as it happens (its reasoning, each step it takes and
  any change it proposes), so a slow model never leaves the person guessing.

  Background:
    Given Alice can view and change customers
    And a customer "Acme" with status "active"
    And Alice is looking at "Acme"
    And Alice opened the assistant
    And Alice started a new conversation

  Scenario: A turn streams the reasoning, each step and the answer
    Given the assistant will think "Checking the record." first
    And the assistant will call get_object
    And the assistant will reply "Acme is active."
    When Alice asks the assistant "how is Acme doing?"
    Then Alice sees the turn:
      | event                | detail                  |
      | the turn starts      |                         |
      | the assistant thinks | Checking the record.    |
      | a step starts        | Reading the open record |
      | the step ends        | succeeded               |
      | the assistant writes | Acme is active.         |
      | the answer arrives   | Acme is active.         |
      | the turn ends        |                         |

  Scenario: A step that fails is shown as failed
    Given the assistant will call get_object for "Acme"
    And Alice may no longer view customers
    When Alice asks the assistant "how is Acme doing?"
    Then Alice sees the turn:
      | event                | detail       |
      | the turn starts      |              |
      | a step starts        | Reading Acme |
      | the step ends        | failed       |
      | the assistant writes | Done.        |
      | the answer arrives   | Done.        |
      | the turn ends        |              |

  Scenario: A proposed change appears as a card and changes nothing yet
    Given the assistant will call propose_patch with:
      | set status | churned |
    And the assistant will reply "I proposed churning Acme."
    When Alice asks the assistant "churn this customer"
    Then Alice sees the turn:
      | event                | detail                               |
      | the turn starts      |                                      |
      | a step starts        | Drafting a change to the open record |
      | the step ends        | succeeded                            |
      | a card appears       | for Acme                             |
      | the assistant writes | I proposed churning Acme.            |
      | the answer arrives   | I proposed churning Acme.            |
      | the turn ends        |                                      |
    And the assistant has proposed changing the status of "Acme" to "churned"
    And "Acme" still has status "active"

  Scenario: The conversation keeps the message, the steps, the card and the answer
    Given the assistant will call propose_patch with:
      | set status | churned |
    And the assistant will reply "I proposed churning Acme."
    And Alice asked the assistant "churn this customer"
    When Alice comes back and reopens that conversation
    Then the conversation shows:
      | who       | what                                 |
      | user      | churn this customer                  |
      | activity  | Drafting a change to the open record |
      | proposal  | pending                              |
      | assistant | I proposed churning Acme.            |

  Scenario: Without an AI model the assistant says it is not available
    Given no AI model is configured
    When Alice asks the assistant "hello?"
    Then the assistant answers "The assistant is not available: no AI model is configured for this installation."

  Scenario: When the AI model fails, the person sees an error and the conversation records it
    Given the AI model is down
    When Alice asks the assistant "hello?"
    Then Alice sees the error "The assistant ran into an error."
    When Alice comes back and reopens that conversation
    Then the conversation shows:
      | who    | what                                    |
      | user   | hello?                                  |
      | system | Error: The assistant ran into an error. |

  Scenario: A card can be confirmed while the assistant is still writing its answer
    Given the assistant will call propose_patch with:
      | set status | churned |
    And the assistant takes its time to finish after proposing
    When Alice asks the assistant "churn this customer" and a card appears
    And Alice confirms the card
    Then the card says "Applied fields: status"
    And "Acme" has status "churned"
    And the assistant is still answering
