@check:crudkit.E005 @endpoint:records.retrieve @endpoint:records.partial_update @endpoint:records.metadata
Feature: Only some people may see or change a field
  Some fields are sensitive: special terms on a deal should only be filled in
  by Legal or the CEO, and some margins are not for everyone's eyes. A project
  marks such a field, and each one gets its own permission. Administrators give
  that permission to groups (roles such as Legal or CEO) or to people, as they
  do with any other permission. Everywhere the app shows or writes records, the
  field is then hidden or read-only for everyone else.

  Background:
    Given Alice can view and change customers
    And Alice is in the group "Legal"
    And Bob can view and change customers
    And a customer "Acme" with email "legal@acme.test"

  Rule: A field only some people may change is read-only for the rest

    Background:
      Given only some people may change the email of customers
      And the group "Legal" may change the email of customers

    Scenario: A person whose group has the permission may change the field
      When Alice changes the email of "Acme" to "deals@acme.test"
      Then it succeeds
      And "Acme" has email "deals@acme.test"

    Scenario: Someone without the permission sees the field but may not change it
      When Bob looks at "Acme"
      Then the record shown has the email "legal@acme.test"
      When Bob changes the email of "Acme" to "bob@acme.test"
      Then it is rejected with "You may not change this field."
      And "Acme" still has email "legal@acme.test"

    Scenario: The permission can be given to a person directly
      Given Bob may change the email of customers
      When Bob changes the email of "Acme" to "bob@acme.test"
      Then it succeeds

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

    Scenario: Someone without the permission may not undo a change to the field
      Given Alice changed the email of "Acme" to "deals@acme.test"
      When Bob undoes that change
      Then it is forbidden
      And "Acme" still has email "deals@acme.test"

    Scenario: Changing many records at once may not set the field without the permission
      Given a customer "Globex"
      When Bob sets the email of "Acme" and "Globex" to "bulk@example.com" at once
      Then it is rejected with "You may not change this field."
      And "Acme" still has email "legal@acme.test"

    Scenario: A person who leaves the group loses what it gave them
      Given Alice is no longer in the group "Legal"
      When Alice changes the email of "Acme" to "deals@acme.test"
      Then it is rejected with "You may not change this field."

  Rule: A field only some people may see is hidden from the rest

    Background:
      Given only some people may see the email of customers
      And the group "Legal" may change the email of customers

    Scenario: Someone without the permission does not see the field at all
      When Bob looks at "Acme"
      Then it succeeds
      And the record shown leaves out the email
      When Bob looks up the description of customers
      Then the description leaves out the field "email"

    Scenario: The permission to see the field does not let a person change it
      Given Bob may see the email of customers
      When Bob looks at "Acme"
      Then the record shown has the email "legal@acme.test"
      When Bob changes the email of "Acme" to "bob@acme.test"
      Then it is rejected with "You may not change this field."

    Scenario: Someone without the permission may not write the hidden field
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

    Scenario: A person with the permission still sees and searches the field
      When Alice searches only customers for "legal@acme"
      Then the search finds "Acme"
      When Alice looks at "Acme"
      Then the record shown has the email "legal@acme.test"

    Scenario: An MCP client acting for someone without the permission is not shown the field
      When an MCP client acting for Bob opens "Acme"
      Then the client is not shown the email
      When an MCP client acting for Bob describes customers
      Then the client may not write "email"

  Rule: Everyone else is unaffected

    Scenario: Superusers may always see and change every field
      Given only some people may see the email of customers
      And Carol is a superuser
      When Carol changes the email of "Acme" to "carol@acme.test"
      Then it succeeds

    Scenario: Fields that are not restricted stay open to everyone who may see the record
      Given only some people may change the email of customers
      When Bob changes the status of "Acme" to "churned"
      Then it succeeds

    Scenario: An MCP client acting for someone without the permission may not change the field
      Given only some people may change the email of customers
      And Bob connected an MCP client with write access
      And the server lets MCP clients write directly
      When an MCP client acting for Bob changes the email of "Acme" to "bob@acme.test"
      Then the client is refused with "email"
      And "Acme" still has email "legal@acme.test"

    Scenario: The assistant's description of a record leaves out what the person may not change
      Given only some people may change the email of customers
      When the assistant describes "Acme" for Bob
      Then the record description leaves out email

  Rule: The permissions come from the project's declaration

    Scenario: Each restricted field gets its permissions when the database is set up
      Given only some people may see the email of customers
      When the database is set up
      Then the permission "Can change email of customer" exists
      And the permission "Can view email of customer" exists

    Scenario Outline: A restricted field declared wrongly is reported before the project starts
      Given <mistake>
      When the record types are checked
      Then the record type check fails with "crudkit.E005" saying "<problem>"

      Examples:
        | mistake                                          | problem                                  |
        | customers guard the field "colour"               | names 'colour', which is not a field     |
        | customers guard the email at the level "write"   | use Restrict.edit or Restrict.view       |
