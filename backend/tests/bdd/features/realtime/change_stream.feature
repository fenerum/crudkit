@transactional @websocket:ws/changes/
Feature: Live change hints
  Open browsers keep their lists and pages current without polling: the
  change stream tells them that a record was saved or removed, and they
  fetch it again through the app. Nobody hears about a record they may not
  see.

  Background:
    Given Alice can view customers
    And Bob can view and change customers
    And a customer "Acme"

  Scenario: A signed-in browser is ready to hear changes
    When Alice connects to the change stream
    Then Alice's change stream is ready

  Scenario: A browser can sign in on the stream with its token
    When Alice connects to the change stream with her token
    Then Alice's change stream is ready

  Scenario: Watchers hear who saved a record
    Given Alice is watching the change stream
    When Bob changes the name of "Acme" to "Acme Inc"
    Then Alice hears that "Acme" was saved by Bob
    And Alice hears nothing more

  Scenario: Deleting a record through the app is announced as a change to it
    Given Bob can view, change and delete customers
    And Alice is watching the change stream
    When Bob deletes "Acme"
    Then Alice hears that "Acme" was saved

  @known-bug
  Scenario: Watchers hear who deleted a record through the app
    Given Bob can view, change and delete customers
    And Alice is watching the change stream
    When Bob deletes "Acme"
    Then Alice hears that "Acme" was saved by Bob

  Scenario: A permanent removal is announced without saying which record or who
    Given Alice is watching the change stream
    When "Acme" is permanently removed
    Then Alice hears that a customer was removed

  Scenario: A change that is never saved is not announced
    Given Alice is watching the change stream
    When a change to "Acme" is abandoned before it is saved
    Then Alice hears nothing

  Scenario: Nobody hears about record types they may not view
    Given Bob can view and change topics
    And a topic "Billing"
    And Alice is watching the change stream
    When Bob changes the name of "Billing" to "Invoices"
    Then Alice hears nothing

  Scenario: Nobody hears about individual records they may not view
    Given Alice is watching the change stream
    When Bob proposes changing the name of "Acme" to "Acme Ltd"
    And Alice proposes changing the name of "Acme" to "Acme Inc"
    Then Alice hears that "Alice's proposal" was saved by Alice
    And Alice hears nothing more

  Scenario: Superusers hear about every record
    Given Carol is a superuser
    And Carol is watching the change stream
    When Bob proposes changing the name of "Acme" to "Acme Ltd"
    Then Carol hears that "Bob's proposal" was saved by Bob

  Scenario: Without live updates the stream closes so the browser falls back to polling
    Given live updates are switched off
    When Alice connects to the change stream
    Then Alice's change stream closes because live updates are switched off
