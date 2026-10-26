Feature: Live updates
  Open pages follow changes made elsewhere, by a colleague or an agent,
  without reloading. A form being filled in never loses what was typed: it
  offers to load the other change instead.

  Background:
    Given Alice is signed in
    And a reading "Shared" with pages "100"

  Scenario: An open record page shows a change made elsewhere
    Given Alice has "Shared" open
    When the name of "Shared" is changed to "Shared, renamed" elsewhere
    Then she sees "Shared, renamed"

  Scenario: An open form keeps what was typed when the record changes elsewhere
    Given Alice is editing "Shared"
    When she fills in the name "Shared, mine"
    And the pages of "Shared" are changed to "200" elsewhere
    Then she is told the record changed elsewhere
    And the form still has the name "Shared, mine"

  Scenario: The form can load the change made elsewhere
    Given Alice is editing "Shared"
    When she fills in the name "Shared, mine"
    And the pages of "Shared" are changed to "200" elsewhere
    And she loads the other change
    Then the form has the name "Shared"
    And the form has the pages "200"
