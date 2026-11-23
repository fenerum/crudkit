@type:FLA @endpoint:records.retrieve @endpoint:records.partial_update @endpoint:records.metadata
Feature: Only some roles may see or change a field
  Some fields are sensitive: special terms on a deal should only be filled in
  by Legal or the CEO, and some notes are not for everyone's eyes. An
  administrator gives people roles and says, per field, which roles may see it
  and which may change it. Everywhere the app shows or writes records, the
  field is then hidden or read-only for everyone else.

  Background:
    Given Alice can view and change customers
    And Alice has the role "Legal"
    And Bob can view and change customers
    And a customer "Acme" with email "legal@acme.test"
    And people with the role "Legal" can edit the email of customers

  Rule: A field others may only view is read-only for them

    Background:
      Given everyone else can view the email of customers

    Scenario: A person with the role may change the field
      When Alice changes the email of "Acme" to "deals@acme.test"
      Then it succeeds
      And "Acme" has email "deals@acme.test"

    Scenario: Someone without the role sees the field but may not change it
      When Bob looks at "Acme"
      Then the record shown has the email "legal@acme.test"
      When Bob changes the email of "Acme" to "bob@acme.test"
      Then it is rejected with "You may not change this field."
      And "Acme" still has email "legal@acme.test"

    Scenario: Saving a form that sends the field back unchanged still works
      When Bob saves "Acme" with its email unchanged and the status "churned"
      Then it succeeds
      And "Acme" has status "churned"
      And "Acme" still has email "legal@acme.test"

    Scenario: The description tells the app the field is read-only for that person
      When Bob looks up the description of customers
      Then the field "email" cannot be edited
      When Alice looks up the description of customers
      Then the field "email" can be edited

    Scenario: Someone without the role may not undo a change to the field
      Given Alice changed the email of "Acme" to "deals@acme.test"
      When Bob undoes that change
      Then it is forbidden
      And "Acme" still has email "deals@acme.test"

    Scenario: Changing many records at once may not set the field for someone without the role
      Given a customer "Globex"
      When Bob sets the email of "Acme" and "Globex" to "bulk@example.com" at once
      Then it is rejected with "You may not change this field."
      And "Acme" still has email "legal@acme.test"

  Rule: A field nobody else may view is hidden from them

    Scenario: Someone without the role does not see the field at all
      When Bob looks at "Acme"
      Then it succeeds
      And the record shown leaves out the email
      When Bob looks up the description of customers
      Then the description leaves out the field "email"

    Scenario: Someone without the role may not write the hidden field
      When Bob changes the email of "Acme" to "bob@acme.test"
      Then it is rejected with "You may not change this field."
      And "Acme" still has email "legal@acme.test"

    Scenario: The list can't be searched or filtered by the field
      When Bob searches only customers for "legal@acme"
      Then the search finds nothing
      When Bob lists the customers whose email is "legal@acme.test"
      Then it is rejected with "You may not filter by email."

    Scenario: Asking the list for the field, or to sort by it, is ignored
      Given a customer "Beta" with email "a@beta.test"
      When Bob lists the customers showing only name and email
      Then it succeeds
      And every row of the list shows only name
      When Bob lists the customers sorted by email
      Then the list is ordered "Acme" and "Beta"
      When Alice lists the customers sorted by email
      Then the list is ordered "Beta" and "Acme"

    Scenario: A shared view that shows or sorts by the field still opens, without it
      Given a customer "Beta" with email "a@beta.test"
      And Alice saved a view "Legal list" of customers with:
        | fields   | name and email |
        | order by | email          |
      And Bob can view views
      When Bob opens the view "Legal list" as the app does
      Then it succeeds
      And every row of the list shows only id, label and name
      And the view shows "Acme" and "Beta" in that order

    Scenario: The history does not give away old or new values of the field
      Given Bob can view change logs
      And Alice changed the email of "Acme" to "deals@acme.test"
      And Alice changed the status of "Acme" to "churned"
      When Bob reads the history of "Acme"
      Then the history leaves out the email

    Scenario: A person with the role still sees and searches the field
      When Alice searches only customers for "legal@acme"
      Then the search finds "Acme"
      When Alice looks at "Acme"
      Then the record shown has the email "legal@acme.test"

  Rule: The best rule among a person's roles wins

    Scenario: A person with several roles gets the most access any of them gives
      Given people with the role "Sales" can view the email of customers
      And Bob has the role "Sales"
      And Bob has the role "Legal"
      When Bob changes the email of "Acme" to "bob@acme.test"
      Then it succeeds

    Scenario: A person who leaves the role loses what it gave them
      Given Alice no longer has the role "Legal"
      When Alice looks at "Acme"
      Then the record shown leaves out the email

    Scenario: Superusers may always see and change every field
      Given Carol is a superuser
      When Carol changes the email of "Acme" to "carol@acme.test"
      Then it succeeds

    Scenario: Fields without rules stay open to everyone who may see the record
      When Bob changes the status of "Acme" to "churned"
      Then it succeeds

  Rule: MCP clients and the assistant follow the same rules

    Scenario: An MCP client acting for someone without the role is not shown the hidden field
      When an MCP client acting for Bob opens "Acme"
      Then the client is not shown the email
      When an MCP client acting for Bob describes customers
      Then the client may not write "email"

    Scenario: An MCP client acting for someone without the role may not change the field
      Given everyone else can view the email of customers
      And Bob connected an MCP client with write access
      And the server lets MCP clients write directly
      When an MCP client acting for Bob changes the email of "Acme" to "bob@acme.test"
      Then the client is refused with "email"
      And "Acme" still has email "legal@acme.test"

    Scenario: The assistant's description of a record leaves out what the person may not change
      Given everyone else can view the email of customers
      When the assistant describes "Acme" for Bob
      Then the record description leaves out email
