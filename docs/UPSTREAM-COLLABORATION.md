# Draft for upstream maintainers (not sent)

We maintain a native LoxBerry/Loxone adapter using SmartThings-Local, with mappings
based on LocalThings under MIT. We want to contribute to existing Samsung research.

Our exports use your resources/identity data shape and redaction/encoding helpers,
with additional privacy filtering and explicit adapter/capture limitations. We keep
installation, MQTT and adapter-only problems in our own repository and can replay
your diagnostic resource maps and device0 fixtures offline.

Would reviewed adapter capability reports be welcome in your device-support
template? Which metadata is essential, and would you prefer fixture PRs? We do not
assume you want to maintain LoxBerry or accept adapter support responsibilities.

Would a versioned HA-independent registry and diagnostic contract be useful across
LocalThings, Homey and LoxBerry? We could contribute adapter tests and packaging.
Until there is agreement, we use reviewed pinned adaptations and label differences.
