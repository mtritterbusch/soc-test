import tempfile
import csv
import ast

from django.http import HttpResponseRedirect
from django import forms
from django.shortcuts import render_to_response
from django.template.context_processors import csrf
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

# Could be in library of forms
class CsvFileUploadForm(forms.Form):
    file = forms.FileField(label="Address Book (csv format)")

def handle_uploaded_file(f):
    """Saves uploaded file to temp space (no delete)"""

    #fp = tempfile.NamedTemporaryFile(prefix="addr_", suffix=".csv", dir="/home/marc/uploads/", delete=False)
    fp = tempfile.NamedTemporaryFile(prefix="addr_", suffix=".csv", delete=False)

    for chunk in f.chunks():
        fp.write(chunk)

    fp.close()
    return fp.name

def map_csvfile(csvreader, header):
    """Normalize csv address book to our format for display and storage"""

    # return list of dict items
    # { "name": ..., "addr": ..., "city": ..., "state": ...,
    # "zip": ..., "country": ..., "phone_number": ... }
    fieldnames = csvreader.fieldnames

    name_map = []
    addr_map = []
    city_map = []
    state_map = []
    zip_map = []
    country_map = []
    phone_map = []

    if "name" in fieldnames:
        name_map.append("name")
    # else: # different formats/mappings

    if "address1" in fieldnames:
        addr_map.append("address1")

    if "address2" in fieldnames:
        addr_map.append("address2")

    if "city" in fieldnames:
        city_map.append("city")

    if "state" in fieldnames:
        state_map.append("state")

    if "postal_code" in fieldnames:
        zip_map.append("postal_code")

    if "country" in fieldnames:
        country_map.append("country")

    if "phone_number" in fieldnames:
        phone_map.append("phone_number")

    # now that mappings are set up, start consuming csv
    addr_book = []
    for row in csvreader:
        mapped_row = {}
        mapped_row['name'] = ' '.join([row[x] for x in name_map]).strip()
        mapped_row['addr'] = '\n'.join([row[x] for x in addr_map]).strip()
        mapped_row['city'] = ' '.join([row[x] for x in city_map]).strip()
        mapped_row['state'] = ' '.join([row[x] for x in state_map]).strip()
        mapped_row['zip'] = '-'.join([row[x] for x in zip_map]).strip(' -')
        mapped_row['country'] = ' '.join([row[x] for x in country_map]).strip()
        mapped_row['phone_number'] = '-'.join([row[x] for x in phone_map]).strip()
        mapped_row['number'] = len(addr_book)
        addr_book.append(mapped_row)

    return addr_book

def upload_file(request):
    if request.method == "POST":
        form = CsvFileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            request.session['upload_file'] = handle_uploaded_file(request.FILES['file'])
            try:
                # clear out session var if uploaded a file
                del request.session['preview_file']
            except KeyError:
                pass
            return HttpResponseRedirect('/preview')
    else:
        form = CsvFileUploadForm()

    form_dict = {'form': form}
    form_dict.update(csrf(request))
    return render_to_response('upload.html', form_dict)


def preview_addr_book(request):
    DISPLAY_CONTACTS = 10
    try:
        addr_file = request.session['preview_file']
        # load preview file
        try:
            fp = open(addr_file)
        except IOError:
            # possibly old session, throw error to try and load upload file
            raise KeyError

        contacts_full = []
        for line in fp:
            line = line.rstrip()
            if not line:
                continue
            contacts_full.append(ast.literal_eval(line))
        fp.close()

    except KeyError:
        # we haven't created a scrubbed file yet
        try:
            addr_file = request.session['upload_file']
        except KeyError:
            # no file, so go to upload page
            return HttpResponseRedirect('/upload')

        fp = open(addr_file)

        csvfile = csv.DictReader(fp)
        header = csvfile.next()
        # map_csvfile will parse and extract the fields we need
        contacts_full = map_csvfile(csvfile, header)
        csvfile = None
        fp.close()
        # now rewrite our address book file with our extracted fields
        import os
        os.unlink(addr_file)
        del request.session['upload_file']
        addr_file += ".list"
        request.session['preview_file'] = addr_file
        # now save scrubbed file
        fp = open(addr_file, "wt")
        for contact in contacts_full:
            print >> fp, str(contact)
        fp.close()

    paginator = Paginator(contacts_full, DISPLAY_CONTACTS)

    contact_number = request.GET.get('del')
    if contact_number is not None:
        # mark item for deletion
        try:
            contacts_full[int(contact_number)]['delete'] = '1'
            # now update scrubbed file
            fp = open(addr_file, "wt")
            for contact in contacts_full:
                print >> fp, str(contact)
            fp.close()
        except IndexError:
            # invalid number, just continue
            pass

    contact_number = request.GET.get('undel')
    if contact_number is not None:
        # unmark item for deletion
        try:
            del contacts_full[int(contact_number)]['delete']
            # now update scrubbed file
            fp = open(addr_file, "wt")
            for contact in contacts_full:
                print >> fp, str(contact)
            fp.close()
        except IndexError:
            # invalid number, just continue
            pass

    page = request.GET.get('page')
    try:
        contacts = paginator.page(page)
    except PageNotAnInteger:
        contacts = paginator.page(1)
    except EmptyPage:
        contacts = paginator.page(paginator.num_pages)
    total_contacts = len(contacts_full)
    form_dict = {'contacts': contacts, 'total_contacts': total_contacts, 'display_contacts': DISPLAY_CONTACTS}
    form_dict.update(csrf(request))
    return render_to_response('preview.html', form_dict)
