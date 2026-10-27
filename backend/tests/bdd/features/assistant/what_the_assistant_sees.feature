Feature: What the assistant is told about the screen
  With every message the browser reports what the person has on screen, and
  the assistant is told about it so "this", "these" and "the selected ones"
  mean what the person means. The browser only sends ids: everything is re-read
  with the person's permissions and cut to size, so a tampered report can
  neither reveal a record nor flood the assistant.

  Background:
    Given Alice can view and change customers
    And a customer "Acme"
    And a customer "Beta"
    And a customer "Gamma"

  Scenario: The open record and its tab
    Given Alice is looking at "Acme" on the "notes" tab
    When the assistant reads the screen
    Then the assistant sees "Open record: customer Acme, tab 'notes'."

  Scenario: A list with its saved view, search, filters and page
    Given Alice can view views
    And Alice is looking at the list of customers
    And the list shows Alice's saved view "Churn risk"
    And the list is searched for "ac"
    And the list is filtered on status "active"
    And the list is on page 2
    When the assistant reads the screen
    Then the assistant sees "List of customers"
    And the assistant sees "saved view 'Churn risk'"
    And the assistant sees "search 'ac'"
    And the assistant sees "'status': 'active'"
    And the assistant sees "page 2"

  Scenario: The rows the person sees and has selected
    Given Alice is looking at the list of customers
    And the list shows "Acme, Beta and Gamma"
    And Alice has selected "Beta"
    When the assistant reads the screen
    Then the assistant sees "Visible rows (3): Acme, Beta, Gamma."
    And the assistant sees "Selected rows (1): Beta."

  Scenario: A long list is cut to 100 rows, of which 30 are listed
    Given Alice is looking at the list of customers
    And the list shows 150 customers
    When the assistant reads the screen
    Then the assistant is told about 100 rows but lists only 30

  Scenario: A long search text is cut to 200 characters
    Given Alice is looking at the list of customers
    And the list is searched for a text of 300 characters
    When the assistant reads the screen
    Then the assistant sees a search of 200 characters

  Scenario: At most 20 filters are passed on
    Given Alice is looking at the list of customers
    And the list is filtered on 25 different fields
    When the assistant reads the screen
    Then the assistant sees 20 filters

  Scenario: An open create form, with the values typed into it so far
    Given Alice has a new customer form open with:
      | name   | Delta  |
      | email  |        |
      | status | active |
    When the assistant reads the screen
    Then the assistant sees "Open form: new customer"
    And the assistant sees "not saved yet"
    And the assistant sees "'name': 'Delta'"
    And the assistant sees "'status': 'active'"
    And the assistant does not see "'email'"

  Scenario: An open edit form names the record being edited
    Given Alice has the edit form of "Acme" open
    When the assistant reads the screen
    Then the assistant sees "Open form: editing customer Acme, not saved yet. Current values: none."

  Scenario: Form values are cut to 100 values of 500 characters
    Given Alice has a new customer form open with 150 values of 900 characters
    When the assistant reads the screen
    Then the assistant sees 100 form values of 500 characters

  Scenario: An edit form that points at a record of another type is ignored
    Given Alice has a ticket edit form open that points at "Acme"
    When the assistant reads the screen
    Then the assistant does not see "Open form"

  Scenario: A record the person may not see is not described, whatever the browser says
    Given Bob can view tickets
    And Bob is looking at "Acme"
    When the assistant reads the screen
    Then the assistant does not see "Acme"
    And the assistant sees "Page: detail (/)."

  Scenario Outline: Other pages are named by what they are
    Given Alice is looking at the <page> page
    When the assistant reads the screen
    Then the assistant sees "Page: <described as>"

    Examples:
      | page      | described as           |
      | dashboard | dashboard (/dashboard) |
      | inbox     | inbox (/inbox)         |
      | settings  | other (/settings)      |

  Scenario: The record type's playbook comes with the screen
    Given the playbook for customers is "Always check the balance before proposing a discount."
    And Alice is looking at "Acme"
    When the assistant reads the screen
    Then the assistant sees "Playbook for customers:"
    And the assistant sees "Always check the balance before proposing a discount."
