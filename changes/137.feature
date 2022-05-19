Gracefully handle bad Get* state variable actions

Some devices don't support all the Get* actions (e.g.
GetTransportSettings) that return state variables. This could cause
exceptions when trying to poll variables during an (initial) update. Now
when an expected (state variable polling) action is missing, or gives a
response error, it is logged but no exception is raised. (@chishm)
