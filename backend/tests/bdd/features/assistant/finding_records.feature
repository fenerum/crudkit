@assistant-tool:search @assistant-tool:describe_types @assistant-tool:list_records @assistant-tool:aggregate_records @assistant-tool:get_record @assistant-tool:get_screen_rows
Feature: The assistant finds, lists and counts records
  Beyond the record on screen, the assistant can search, list and count
  records of any type the person may view, read the rows on their screen, and
  look up what a record type is made of. These tools work as they do for MCP
  clients, with the permissions of the person using the assistant.

  Background:
    Given Alice can view and change customers
    And a customer "Acme" with status "active"
    And a customer "Beta" with status "churned"
    And a customer "Gamma" with status "churned"
    And Alice is chatting with the assistant

  Scenario: search finds records among the types the person may view
    Given a ticket "Acme cannot log in"
    When the assistant calls search with:
      | query | Acme |
    Then the assistant gets the records "Acme"

  Scenario: describe_types lists the record types the person may view
    When the assistant calls describe_types
    Then the assistant learns about the record types "customers"
    And the assistant does not learn about the record types "tickets, assistant proposals and change logs"

  Scenario: describe_types describes one type's writable fields and whether the person may create one
    When the assistant calls describe_types with:
      | type | customers |
    Then the assistant learns the writable fields "name, email, status, topic, owner, balance and currency"
    And the assistant learns that Alice may not create customers

  Scenario: describe_types refuses a type that does not exist
    When the assistant calls describe_types with:
      | type | spaceships |
    Then the assistant is refused with "Unknown type 'spaceships'"

  Scenario: list_records lists a type's records with just the columns asked for
    When the assistant calls list_records with:
      | type   | customers |
      | fields | name      |
    Then the assistant gets the records "Acme, Beta and Gamma"
    And the assistant reads only the columns "id, label and name"

  Scenario: list_records filters the records
    When the assistant calls list_records with:
      | type          | customers |
      | filter status | churned   |
    Then the assistant gets the records "Beta and Gamma"

  Scenario: list_records lists the records of a saved view
    Given Alice can view views
    And Alice is looking at the list of customers
    And the list shows Alice's saved view "Everyone"
    When the assistant calls list_records with:
      | view | Everyone |
    Then the assistant gets the records "Acme, Beta and Gamma"

  Scenario: list_records refuses a type the person may not view
    When the assistant calls list_records with:
      | type | tickets |
    Then the assistant is refused with "Permission denied."

  Scenario: aggregate_records counts records grouped by a field
    When the assistant calls aggregate_records with:
      | type     | customers |
      | group by | status    |
    Then the assistant gets the groups:
      | status  | count |
      | active  | 1     |
      | churned | 2     |

  Scenario: aggregate_records refuses a grouping it cannot make
    When the assistant calls aggregate_records with:
      | type     | customers |
      | group by | mood      |
    Then the assistant is refused with "Cannot group by 'mood'"

  Scenario: get_record reads a record with its activity and the actions the person may run
    Given a note "Called about the renewal" was left on "Acme"
    When the assistant calls get_record with:
      | record | Acme |
    Then the assistant is told "Called about the renewal"
    And the assistant is told "mark_churned"

  Scenario: get_record reads only the fields asked for
    When the assistant calls get_record with:
      | record | Acme            |
      | fields | name and status |
    Then the assistant reads only the columns "id, label, name and status"

  Scenario Outline: get_screen_rows reads the <which> rows
    Given Alice is looking at the list of customers
    And the list shows "Acme, Beta and Gamma"
    And Alice has selected "Beta"
    When the assistant calls get_screen_rows with:
      | which | <which> |
    Then the assistant gets the records "<rows>"

    Examples:
      | which    | rows                 |
      | selected | Beta                 |
      | visible  | Acme, Beta and Gamma |

  Scenario: get_screen_rows reads the visible rows when nothing is selected
    Given Alice is looking at the list of customers
    And the list shows "Acme and Beta"
    When the assistant calls get_screen_rows
    Then the assistant gets the records "Acme and Beta"

  Scenario: get_screen_rows leaves out rows the person may not see
    Given Alice is looking at the list of customers
    And the list shows "Acme, Beta and Gamma"
    And Alice may no longer view customers
    When the assistant calls get_screen_rows
    Then the assistant gets no records
