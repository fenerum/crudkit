@endpoint:user_profile
Feature: The signed-in person's profile
  The app shows the signed-in person's name, picture and language, and
  whether the assistant is available to them. A project keeps the language
  and pictures in its own user profiles; CrudKit asks it for them.

  Background:
    Given Alice is a user without any permissions

  Scenario: Without profiles, everyone reads the app in English and has no picture
    When Alice views her profile
    Then the profile is Alice's
    And the profile shows the language "en"
    And the profile shows no pictures

  Scenario: Without profiles, choosing a language changes nothing
    When Alice changes her language to "da"
    Then it succeeds
    And the profile shows the language "en"

  Scenario: A chosen language is kept in the project's profiles
    Given the project keeps people's profiles
    When Alice changes her language to "da"
    And Alice views her profile
    Then the profile shows the language "da"

  Scenario: Only safe pictures are shown, with their full address
    Given the project keeps people's profiles
    And Alice's profile lists the pictures:
      | /media/alice.png                |
      | https://cdn.example.test/a.png  |
      | /etc/passwd                     |
      | javascript:alert(1)             |
    When Alice views her profile
    Then the profile shows the pictures:
      | http://testserver/media/alice.png |
      | https://cdn.example.test/a.png    |

  Scenario: The pictures of the people on a record are shown with their full address
    Given the project keeps people's profiles
    And Alice's profile lists the pictures:
      | /media/alice.png |
    And Alice can view customers
    And Alice owns a customer "Acme"
    When Alice looks at "Acme"
    Then the creator's picture on the record is shown as "http://testserver/media/alice.png"

  Scenario: The assistant is available when an AI model is set up
    Given the assistant is called "Ada" and pictured at "/static/ada.png"
    When Alice views her profile
    Then the profile says the assistant is available
    And the profile names the assistant "Ada" pictured at "/static/ada.png"

  Scenario: Without an AI model the assistant is unavailable, but proposals can still be reviewed
    Given the project has no AI model set up
    When Alice views her profile
    Then the profile says the assistant is not available
    And the profile says proposals can be reviewed

  Scenario: The profile needs signing in
    When someone who is not signed in views a profile
    Then it requires signing in
