@assistant-tool:get_object @assistant-tool:describe_object @assistant-tool:get_changelog @assistant-tool:get_feed @assistant-tool:get_related
Feature: The assistant reads the record on screen
  To answer questions about a record, the assistant reads it, what can be
  changed on it, its history, its activity and the records pointing at it.
  These tools read the record open on screen unless the assistant names
  another, and they only ever see what the person using the assistant may see.

  Background:
    Given Alice can view and change customers
    And a customer "Acme" with status "active"
    And Alice is looking at "Acme"

  Scenario: get_object reads the record on screen
    When the assistant calls get_object
    Then the assistant is told "customer Acme"
    And the assistant is told "status: active"

  Scenario: get_object reads another record when the assistant names it
    Given a customer "Beta" with email "hello@beta.test"
    When the assistant calls get_object for "Beta"
    Then the assistant is told "customer Beta"
    And the assistant is told "email: hello@beta.test"

  Scenario Outline: <tool> needs a record when none is open
    Given Alice is chatting with the assistant
    When the assistant calls <tool>
    Then the assistant is refused with "No record is open"

    Examples:
      | tool            |
      | get_object      |
      | describe_object |
      | get_changelog   |
      | get_feed        |

  Scenario Outline: <tool> refuses a record the person may not see
    Given Bob can view tickets
    And Bob is looking at "Acme"
    When the assistant calls <tool> for "Acme"
    Then the assistant is refused with "Acme not found, or not available for view."

    Examples:
      | tool            |
      | get_object      |
      | describe_object |
      | get_changelog   |
      | get_feed        |

  Scenario: describe_object tells what can be changed, to what, and which actions can be proposed
    Given Alice can view topics
    And a topic "Billing"
    When the assistant calls describe_object
    Then the assistant learns that status is currently "active"
    And the assistant learns that status can be "active, churned"
    And the assistant learns that topic can point at "Billing"
    And the assistant learns the actions "mark_churned"
    And the assistant does not learn about id, created by, updated by and deleted

  Scenario: describe_object does not list a foreign key's rows when there are more than 50
    Given Alice can view topics
    And there are 51 topics to choose from
    When the assistant calls describe_object
    Then the assistant learns there are too many topics to list for topic

  Scenario: describe_object counts the live records pointing at the record
    Given Alice can view tickets
    And a ticket "Broken login" with customer "Acme"
    And a ticket "Old issue" with:
      | customer | Acme |
      | deleted  | True |
    When the assistant calls describe_object
    Then the assistant learns that 1 ticket points at it through "ticket_set"

  Scenario: Records of a type the person may not view are not counted
    Given a ticket "Broken login" with customer "Acme"
    When the assistant calls describe_object
    Then the assistant learns about no related records

  Scenario: get_changelog tells who changed what, with the change set to undo it by
    Given Alice may read the change history
    And Alice changed the status of "Acme" to "churned"
    When the assistant calls get_changelog
    Then the assistant reads that Alice changed the status of "Acme" from "active" to "churned"

  Scenario: get_changelog needs permission to read the change history
    Given Alice changed the status of "Acme" to "churned"
    When the assistant calls get_changelog
    Then the assistant is refused with "this user may not view change history."

  Scenario: get_feed reads the notes on the record
    Given a note "Called about the renewal" was left on "Acme"
    When the assistant calls get_feed
    Then the assistant reads the note "Called about the renewal"

  Scenario Outline: get_related lists the live records pointing at the record, by <named by>
    Given Alice can view tickets
    And a ticket "Broken login" with customer "Acme"
    And a ticket "Old issue" with:
      | customer | Acme |
      | deleted  | True |
    When the assistant calls get_related with:
      | relation name | <relation> |
    Then the assistant gets the records "Broken login"
    And the assistant is told "Subject: Broken login"

    Examples:
      | named by          | relation   |
      | its accessor name | ticket_set |
      | its field name    | ticket     |
      | its record type   | TIC        |

  Scenario: get_related lists the valid relations when given an unknown one
    Given Alice can view tickets
    When the assistant calls get_related with:
      | relation name | invoices |
    Then the assistant is refused with "Unknown relation 'invoices'. Valid: ['ticket_set (TIC)']"

  Scenario: get_related does not follow relations to records the person may not view
    Given a ticket "Broken login" with customer "Acme"
    When the assistant calls get_related with:
      | relation name | ticket_set |
    Then the assistant is refused with "Unknown relation 'ticket_set'. Valid: []"
