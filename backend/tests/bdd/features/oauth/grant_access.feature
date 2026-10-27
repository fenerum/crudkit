@endpoint:crudkit_mcp_oauth_authorize
Feature: A person grants an MCP client access
  Before an MCP client may act for someone, that person signs in and sees a
  consent page naming the client. They choose how much it may do: only read,
  propose changes for them to confirm, or (where the server allows it) write
  directly. Reading is always part of the deal.

  Background:
    Given Alice is a user without any permissions
    And an MCP client "Claude" is registered

  Scenario: The consent page names the client and the person
    When Alice opens the consent page for "Claude"
    Then Alice is asked whether "Claude" may access her data

  Scenario: Only signed-in people see the consent page
    When someone who is not signed in opens the consent page for "Claude"
    Then they are sent to sign in first

  Scenario Outline: A malformed request for access is refused
    When Alice opens the consent page for "Claude" with <parameter> "<value>"
    Then it is rejected with "<message>"

    Examples:
      | parameter        | value   | message                                                  |
      | code challenge   |         | Missing required parameters                              |
      | response type    | token   | Unsupported response_type, must be 'code'                |
      | challenge method | plain   | Unsupported code_challenge_method, must be 'S256'        |
      | client id        | unknown | Invalid client_id                                        |
      | scope            | admin   | Unsupported scope: admin                                 |

  Scenario: A redirect address the client did not register is refused
    When Alice opens the consent page for "Claude" with a redirect address it did not register
    Then it is rejected with "Invalid redirect_uri"

  Scenario: A deactivated client cannot ask for access
    Given the MCP client "Claude" has been deactivated
    When Alice opens the consent page for "Claude"
    Then it is rejected with "Client is inactive"

  Scenario: Without a requested scope every kind of access is offered
    Given the server lets MCP clients write directly
    When Alice opens the consent page for "Claude"
    Then the consent page offers "Read only", "Propose changes" and "Write directly"

  Scenario: Writing directly is not offered when the server does not allow it
    When Alice opens the consent page for "Claude"
    Then the consent page offers "Read only" and "Propose changes"

  Scenario: Only the access the client asked for is offered
    Given the server lets MCP clients write directly
    And "Claude" asks for "read propose" access
    When Alice opens the consent page for "Claude"
    Then the consent page offers "Read only" and "Propose changes"

  Scenario: A client that only asked to read is only offered reading
    Given "Claude" asks for "read" access
    When Alice opens the consent page for "Claude"
    Then the consent page offers "Read only"

  Scenario: Asking to write is refused when the server does not allow it
    Given "Claude" asks for "read write" access
    When Alice allows "Claude" with "write" access
    Then it is rejected with "Unsupported scope: write"
    And no authorization code is issued

  Scenario: Allowing access sends the client back with a short-lived code
    When Alice allows "Claude" with "read" access
    Then "Claude" is sent back with an authorization code
    And the authorization code grants "read"
    And the authorization code is valid for 10 minutes

  Scenario: Denying access tells the client so
    When Alice denies "Claude" access
    Then "Claude" is sent back with the error "access_denied"

  Scenario: The client gets its state back unchanged
    Given "Claude" passes the state "a=1&b=2"
    When Alice allows "Claude" with "read" access
    Then "Claude" gets back the state "a=1&b=2"

  Scenario Outline: The client gets the access Alice picked, if it asked for it
    Given "Claude" asks for "<requested>" access
    When Alice allows "Claude" with "<picked>" access
    Then the authorization code grants "<granted>"

    Examples:
      | requested    | picked  | granted      |
      | read propose | propose | read propose |
      | read         | propose | read         |
      | read propose | admin   | read         |

  Scenario Outline: With direct writing allowed, the client gets the access Alice picked, if it asked for it
    Given the server lets MCP clients write directly
    And "Claude" asks for "<requested>" access
    When Alice allows "Claude" with "<picked>" access
    Then the authorization code grants "<granted>"

    Examples:
      | requested  | picked  | granted      |
      | read write | write   | read write   |
      | write      | write   | read write   |
      | read write | propose | read propose |
      | read       | write   | read         |

  Scenario: A client that asked for nothing in particular may be given propose access
    When Alice allows "Claude" with "propose" access
    Then the authorization code grants "read propose"

  Scenario: Direct writing is never granted when the server does not allow it
    When Alice allows "Claude" with "write" access
    Then the authorization code grants "read"

  Scenario: Allowing without picking grants read access only
    Given the server lets MCP clients write directly
    When Alice allows "Claude" without picking an access level
    Then the authorization code grants "read"
