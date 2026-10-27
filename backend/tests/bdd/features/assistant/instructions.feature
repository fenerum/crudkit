Feature: The assistant's instructions and tools
  Every turn starts from the same instructions: the project's own prompt, the
  assistant's name, how to work with records and proposals, and the company
  context documents for what is on screen. The tools it is offered decide what
  it can read and what it can only propose.

  Background:
    Given Alice can view and change customers
    And a customer "Acme"
    And Alice is looking at "Acme"

  Scenario: The project's prompt comes first, then the assistant's name
    Given the project's assistant prompt is "You work for Initech."
    And the assistant is called "Ada"
    When Alice asks the assistant "hello"
    Then the assistant's instructions start with "You work for Initech."
    And the assistant's instructions say, in this order:
      | You work for Initech.                      |
      | Your name is Ada.                          |
      | You are an AI assistant in a sidebar       |
      | Each user message starts with a `[Screen]` |
      | Proposals do NOT take effect immediately   |
      | In this chat you also have two form tools  |
      | Style:                                     |

  Scenario: Unless the project names it, the assistant is called Assistant
    When Alice asks the assistant "hello"
    Then the assistant's instructions start with "Your name is Assistant."

  Scenario: The company context covers everything plus the record type on screen
    Given an AI context document "Ideal customer" saying "Small agencies."
    And an AI context document "Churn playbook" for customers saying "Call before renewal."
    And an AI context document "Ticket triage" for tickets saying "Billing first."
    When Alice asks the assistant "hello"
    Then the assistant's instructions say, in this order:
      | Style:            |
      | # Company context |
    And the assistant's instructions include the AI context "Ideal customer"
    And the assistant's instructions include the AI context "Churn playbook"
    And the assistant's instructions do not include the AI context "Ticket triage"
    And the assistant does not see "Call before renewal."

  Scenario: The assistant in the chat is offered every tool
    When Alice asks the assistant "hello"
    Then the assistant is offered exactly these tools:
      | get_object          |
      | describe_object     |
      | get_changelog       |
      | get_feed            |
      | get_related         |
      | search              |
      | describe_types      |
      | list_records        |
      | aggregate_records   |
      | get_record          |
      | get_screen_rows     |
      | propose_patch       |
      | propose_bulk_patch  |
      | propose_action      |
      | propose_create_note |
      | propose_create      |
      | propose_revert      |
      | fill_form           |
      | open_create_form    |

  Scenario: A record type's own assistant tools are offered when that type is on screen
    Given customers have their own assistant tool check_credit
    When Alice asks the assistant "can they pay?"
    Then the assistant is offered check_credit

  Scenario: A record type's own tools and the form tools are never offered to background agents
    Given customers have their own assistant tool check_credit
    When a background agent works on "Acme" for Alice
    Then the assistant is not offered check_credit, fill_form and open_create_form
    And the assistant's instructions do not mention "In this chat you also have two form tools"

  Scenario: The assistant answers with a low temperature
    When Alice asks the assistant "hello"
    Then the assistant works with a temperature of 0.2

  Scenario Outline: A tool name the model garbles is still understood
    Given the assistant will call get_object for "Acme" with its name garbled by <garble>
    When Alice asks the assistant "what is this?"
    Then the tool get_object ran

    Examples:
      | garble                   |
      | invisible tag characters |
      | its arguments glued on   |
      | a trailing space         |
      | empty brackets           |
