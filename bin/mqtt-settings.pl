#!/usr/bin/perl
use strict;
use warnings;
use FindBin;
use lib "$FindBin::Bin/../../../libs/perllib";
use LoxBerry::IO;
use JSON::PP;
# Private pipe to the daemon, never a web endpoint or log entry.
my $settings = LoxBerry::IO::mqtt_connectiondetails();
die "MQTT settings unavailable\n" unless $settings && $settings->{brokerhost};
print encode_json($settings);
