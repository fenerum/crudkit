@type:AIC
Feature: AI context documents
  Teams write down what every AI feature should know (who their customers
  are, their tone of voice, how to triage) as AI context documents. Each AI
  run reads the documents that are switched on and apply to the record's
  type, in the order the team chose.

  Background:
    Given a ticket "Refund please"
    And the AI answers:
      | field   | value   |
      | summary | Refund. |

  Scenario: Each document is given to the AI under its name
    Given an AI context document "Ideal customer" saying "Small agencies."
    When the AI fields of "Refund please" are filled in
    Then the AI read this AI context:
      """
      ## Ideal customer
      Small agencies.
      """

  Scenario: Documents are read in their order, then by name
    Given the AI context documents:
      | name              | body                | order |
      | Tone of voice     | Plain and friendly. | 2     |
      | Why customers buy | Speed.              | 1     |
      | Ideal customer    | Small agencies.     | 1     |
    When the AI fields of "Refund please" are filled in
    Then the AI read the AI context documents in this order:
      | Ideal customer    |
      | Why customers buy |
      | Tone of voice     |

  Scenario: Only documents for everything or for this record type are read
    Given the AI context documents:
      | name           | body                        | for                   |
      | Everywhere     | Be kind.                    |                       |
      | Ticket triage  | Billing issues are urgent.  | tickets and customers |
      | Churn playbook | Offer a discount.           | customers             |
    When the AI fields of "Refund please" are filled in
    Then the AI read the AI context documents in this order:
      | Everywhere    |
      | Ticket triage |

  Scenario: Switched-off and deleted documents are not read
    Given the AI context documents:
      | name   | body        |
      | Live   | Current.    |
      | Draft  | Not yet.    |
      | Old    | Superseded. |
    And the AI context document "Draft" is switched off
    And the AI context document "Old" is deleted
    When the AI fields of "Refund please" are filled in
    Then the AI read the AI context documents in this order:
      | Live |

  Scenario: Without any documents the AI reads only the record
    When the AI fields of "Refund please" are filled in
    Then the AI read no AI context

  Scenario: Very long AI context is cut off
    Given the AI context may be at most 40 characters long
    And an AI context document "Handbook" saying "Everything about how we work, at great length."
    When the AI fields of "Refund please" are filled in
    Then the AI read only the first 40 characters of the AI context, marked as truncated

  Scenario: A document can be scoped to record types
    Given Alice is a superuser
    When Alice adds an AI context document "Pricing" for tickets and customers
    Then it succeeds
    And the AI context document "Pricing" applies to tickets and customers

  Scenario: A document cannot be scoped to a record type that does not exist
    Given Alice is a superuser
    When Alice adds an AI context document "Pricing" for the unknown record type "XYZ"
    Then it is rejected with "Unknown record types"

  Scenario: The record types of a document must be a list
    Given Alice is a superuser
    When Alice adds an AI context document "Pricing" with its record types as plain text "TIC"
    Then it is rejected with "Format:"
