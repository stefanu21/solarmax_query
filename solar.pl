#!/usr/bin/perl -w

# lightygraph -- a lighttpd statistics rrdtool frontend
# copyright (c) 2008 Joe Nahmias <joe@nahmias.net>
# based on mailgraph by David Schweikert <dws@ee.ethz.ch>
# released under the GNU General Public License

# /usr/lib/cgi-bin/solar.pl

use RRDs;
use POSIX qw(uname);

my $VERSION = "0.50";

my $host = (POSIX::uname())[1];
my $scriptname = 'solar';
my $xpoints = 600;
my $ypoints = 350;
my $rrd = '/var/www/solar.rrd';   # path to where the RRD database is
my $tmp_dir = '/var/cache/lighttpd'; # temporary directory where to store the images

my @graphs = (
	{ title => 'Last 4 Hours',   seconds => 60 * 60 *  4     ,   },
	{ title => 'Daily Graphs',   seconds => 60 * 60 * 24     ,   },
	{ title => 'Monthly Graphs', seconds => 60 * 60 * 24 * 30,   },
);

my %color = (         # rrggbb in hex
	areamin     => 'ffffff',
	instack     => 'f00000',
	minmax      => 'a0a0a0',
	incoming    => 'efb71d', 
	outstack    => '00f000',
	outgoing    => 'a0a735',
	reqstack    => '00f000',
	requests    => '00a735',
);

sub rrd_graph(@)
{
	my ($range, $file, $ypoints, @rrdargs) = @_;
	# choose carefully the end otherwise rrd will maybe pick the wrong RRA:
	my $date = localtime(time);
	$date =~ s|:|\\:|g unless $RRDs::VERSION < 1.199908;

	my ($graphret,$xs,$ys) = RRDs::graph($file,
		'--imgformat', 'PNG',
		'--width', $xpoints,
		'--height', $ypoints,
		'--start', "-$range",
		'--lazy',

		@rrdargs,

		'COMMENT:['.$date.']\r',
	);

	my $ERR=RRDs::error;
	die "ERROR: $ERR\n" if $ERR;
}

sub graph_traffic($$)
{
	my ($range, $file) = @_;
	rrd_graph($range, $file, $ypoints,
	    "-t Solardata",
            "DEF:ac=$rrd:ac_power:AVERAGE",
	    "VDEF:acl=ac,LAST",
	    "VDEF:acm=ac,MAXIMUM",
            "LINE2:ac#$color{incoming}:ac",
	    "GPRINT:acl:aktuell %5.2lf kW",
	    "GPRINT:acm:max. %5.2lf kW",
	);
}

sub print_html()
{
	print "Content-Type: text/html\n\n";

	print <<HEADER;
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN" "http://www.w3.org/TR/REC-html40/loose.dtd">
<HTML>
<HEAD>
<TITLE>Bernd's Solaranlage</TITLE>
<META HTTP-EQUIV="Refresh" CONTENT="300">
<META HTTP-EQUIV="Pragma" CONTENT="no-cache">
</HEAD>
<BODY BGCOLOR="#FFFFFF">
HEADER

	print "<H1>Meine Solaranlage</H1>\n";
	for my $n (0..$#graphs) {
		print '<div style="background: #dddddd; width: 632px">';
		print "<H2>$graphs[$n]{title}</H2>\n";
		print "</div>\n";
		print "<P><IMG BORDER=\"0\" SRC=\"$scriptname.pl?${n}-t\" ALT=\"$scriptname\">\n";
	}

	print "</BODY></HTML>\n";
}

sub send_image($)
{
	my ($file)= @_;

	-r $file or do {
		print "Content-type: text/plain\n\nERROR: can't find $file\n";
		exit 1;
	};

	print "Content-type: image/png\n";
	print "Content-length: ".((stat($file))[7])."\n";
	print "\n";
	open(IMG, $file) or die;
	my $data;
	print $data while read(IMG, $data, 16384)>0;
}

sub main()
{
	my $uri = $ENV{REQUEST_URI} || '';
	$uri =~ s/\/[^\/]+$//;
	$uri =~ s/\//,/g;
	$uri =~ s/(\~|\%7E)/tilde,/g;
	mkdir $tmp_dir, 0777 unless -d $tmp_dir;

	my $img = $ENV{QUERY_STRING};
	if(defined $img and $img =~ /\S/) {
		if($img =~ /^(\d+)-t$/) {
			my $file = "$tmp_dir/${scriptname}_traffic_$1.png";
			graph_traffic($graphs[$1]{seconds}, $file);
			send_image($file);
		}
		else {
			die "ERROR: invalid argument\n";
		}
	}
	else {
		print_html;
	}
}

main;
