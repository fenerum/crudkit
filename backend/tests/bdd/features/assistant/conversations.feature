@type:ASC @websocket:ws/assistant/ @transactional
Feature: Assistant conversations
  Every chat with the assistant is kept as a conversation that belongs to the
  person who had it, so they can pick it up later where they left off. Nobody
  else can open it.

  Background:
    Given Alice can view and change customers
    And a customer "Acme"
    And Alice opened the assistant

  Scenario: A new conversation starts empty and untitled
    When Alice starts a new conversation
    Then Alice is in a new, empty conversation

  Scenario: A conversation is kept from the first message, which becomes its title
    Given the assistant will reply "Hi Alice."
    When Alice asks the assistant "Hello there"
    Then Alice's conversation is titled "Hello there"

  Scenario: A long first message is cut short for the title
    When Alice asks the assistant a question of 150 characters
    Then the conversation is titled with the first 120 characters of the question

  Scenario: A person picks up their own conversation where they left off
    Given the assistant will reply "Noted."
    And Alice started a new conversation
    And Alice asked the assistant "My favourite customer is Acme"
    When Alice comes back and reopens that conversation
    Then the conversation shows:
      | who       | what                          |
      | user      | My favourite customer is Acme |
      | assistant | Noted.                        |
    When Alice asks the assistant "Who is my favourite?"
    Then the assistant remembers "My favourite customer is Acme"

  Scenario: Someone else's conversation is never reopened
    Given Bob is a user without any permissions
    And Bob has a conversation "Bob's secret plan"
    When Alice reopens the conversation "Bob's secret plan"
    Then Alice is in a new, empty conversation

  Scenario: A deleted conversation is not reopened
    Given Alice has a conversation "Old chat"
    And Alice deleted the conversation "Old chat"
    When Alice reopens the conversation "Old chat"
    Then Alice is in a new, empty conversation

  Scenario: A conversation whose saved memory can no longer be read still shows what was said
    Given Alice has a conversation "Renewal" whose memory can no longer be read
    When Alice reopens the conversation "Renewal"
    Then Alice is in the conversation "Renewal"
    And the conversation shows:
      | who       | what           |
      | user      | About Renewal  |
      | assistant | Happy to help. |
    When Alice asks the assistant "Where were we?"
    Then the assistant remembers nothing earlier
