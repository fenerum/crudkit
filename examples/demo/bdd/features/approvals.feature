@page:/inbox
Feature: Approvals
  Connected apps and agents can propose changes instead of making them. The
  proposals wait in the inbox until someone confirms or skips them, and the
  actions that need such an approval are marked in the menu.

  Background:
    Given Alice is signed in
    And a reading "Proposal target"
    And a pending proposal to change the name of "Proposal target" to "Proposal target renamed"

  Scenario: The inbox shows what a proposal would change
    When Alice opens the proposals in her inbox
    Then the proposal for "Proposal target" would set name to "Proposal target renamed"

  Scenario: Confirming a proposal makes the change
    When Alice confirms the proposal for "Proposal target" in her inbox
    Then the proposal for "Proposal target" leaves the inbox
    When she opens "Proposal target"
    Then she sees "Proposal target renamed"

  Scenario: Skipping a proposal leaves the record as it was
    When Alice skips the proposal for "Proposal target" in her inbox
    Then the proposal for "Proposal target" leaves the inbox
    When she opens "Proposal target"
    Then its name is "Proposal target"

  Scenario: Actions that need approval are marked in the menu
    When Alice opens the actions menu of "Proposal target"
    Then "Mark finished" in the menu says "Connected apps and agents need your approval to run this"
