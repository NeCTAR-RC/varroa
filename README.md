# Varroa

Varroa is a security related openstack service. It is named after the varroa mite
which could be considered a vulnerability to bees.
It has several functions:

 * Track IP ownership over time in openstack
 * Store and manage discovered security risks from openstack resources.

It's main/initial purpose is to ingest security scan data, link these IP addresses to
openstack resources and provide the ability for the owners of those resources to see
these security risks.

## Client
To install the client:
 pip install varroaclient

Source: https://github.com/NeCTAR-RC/python-varroaclient

## Concepts

### IP Usage
Varroa will keep track of what openstack resource owned an IP address for what period.
It does this by consuming port create/update/delete events from neutron.

### Security Risk Type
A security risk type is an admin defined type of security risk. An example could be "Password SSH allowed"

A security risk type has a name and a description. The description should describe what the security risk is
and ideally the steps taken to fix this risk.

### Security Risk
A security risk is the linkage of a security risk type to an openstack resource.
eg. Compute instance with id XYZ has a "Password SSH allowed" security risk.

Only the IP address of the affected resource needs to be entered when creating a new security risk. Varroa
will then process this entry and attempt to link that IP address to an Openstack resource.

#### Security Risk workflow/states

When you create a new security risk it will have the initial state of NEW.
Varroa will attempt to link all NEW security risks with an openstack resource.
If varroa finds a matching resource then it will add these details to the security risk
Once varroa has attempted to link the IP to a resource it will change the status of the
security risk to PROCESSED. If project_id/resource_id is null and status = PROCESSED it
means varroa couldn't find a matching resource.

## Installation
You can install varroa using helm onto a k8s cluster
see https://github.com/NeCTAR-RC/varroa-helm

