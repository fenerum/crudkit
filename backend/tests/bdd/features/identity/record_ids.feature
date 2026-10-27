@field:CrudKitIDField
Feature: Record IDs
  Every record has a short ID made of its record type's three letters and its
  number, like "CUS12", so people can read it out, paste it into search, and
  always tell what kind of record it names. Links between records carry these
  IDs too.

  Background:
    Given Alice is a superuser
    And a topic "Billing"
    And a customer "Acme" with topic "Billing"

  Scenario: A record is shown with its type's letters in front of its number
    When Alice looks at "Acme"
    Then "Acme" is shown with the ID "CUS" followed by its number

  Scenario: A linked record is shown with its own type's letters
    When Alice looks at "Acme"
    Then the topic is shown with the ID of "Billing"

  Scenario: A record can be opened by its number alone
    When Alice opens "Acme" by its number
    Then the record shown is "Acme"

  Scenario Outline: A record can be looked up by its ID or its number
    When a customer is looked up by <how>
    Then the lookup finds "Acme"

    Examples:
      | how                                   |
      | the ID of "Acme"                      |
      | the number of "Acme"                  |
      | the number of "Acme" written as text  |

  Scenario: An ID with another type's letters is refused
    When a customer is looked up by the number of "Acme" with the letters of a topic
    Then the lookup is refused with "Expected a CUS ID, got TOP"

  Scenario: Opening another type's ID as a customer finds nothing
    When Alice opens the ID of "Billing" as a customer
    Then it is not found

  Scenario: An empty ID finds nothing
    When a customer is looked up by an empty ID
    Then the lookup finds nothing

  Scenario: A record type that extends another is shown with its own letters
    Given a ticket "Outage"
    And an urgent comment "Server down" on the ticket "Outage"
    When Alice looks at "Server down"
    Then "Server down" is shown with the ID "URG" followed by its number

  Scenario Outline: A record of an extending type can be found by either type's letters
    Given a ticket "Outage"
    And an urgent comment "Server down" on the ticket "Outage"
    When <lookup>
    Then the lookup finds "Server down"

    Examples:
      | lookup                                                                              |
      | a comment is looked up by the ID of "Server down"                                   |
      | an urgent comment is looked up by the number of "Server down" with the letters of a comment |

  Scenario: An extending type does not accept unrelated letters, naming the type it extends
    Given a ticket "Outage"
    And an urgent comment "Server down" on the ticket "Outage"
    When an urgent comment is looked up by the number of "Server down" with the letters of a ticket
    Then the lookup is refused with "Expected a COM ID, got TIC"
