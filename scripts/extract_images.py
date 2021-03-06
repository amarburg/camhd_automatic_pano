#!/usr/bin/env python3


import glob
import logging
import argparse
import os.path as path
import os
import json
import random
import re

# import region_analysis as ra

import pycamhd.lazycache as camhd
import pycamhd.motionmetadata as mmd

parser = argparse.ArgumentParser(description='Generate HTML proofs')

parser.add_argument('input', nargs='?',
                    help='Regions files to process',
                    default=False)

parser.add_argument('--force', dest='force', action='store_true', help='Force re-download of images')

# parser.add_argument('--squash-runs', dest='squashruns', action='store_true', help='Squash runs of multiple identical tags')

parser.add_argument('--log', metavar='log', nargs='?', default='INFO',
                    help='Logging level')

parser.add_argument('--output', nargs='?', default='images/', help='Working directory')
parser.add_argument('--mov-output-dir', dest='movoutputdir', action='store_true')

parser.add_argument('--image-size', dest='imgsize', nargs='?', default=False)

parser.add_argument('--flatten', default=True, action='store_true')

# parser.add_argument("--ground-truth", dest="groundtruthfile",
#                     default="classification/ground_truth.json")

parser.add_argument("--image-format", dest="imageext", default='png')

parser.add_argument('--lazycache-url', dest='lazycache', default=os.environ.get("LAZYCACHE_URL", None),
                    help='URL to Lazycache repo server (only needed if classifying)')

args = parser.parse_args()
logging.basicConfig( level=args.log.upper() )

qt = camhd.lazycache( args.lazycache )

if args.imgsize:
    img_size = args.imgsize.split('x')
    img_size = ( int(img_size[0]), int(img_size[1]))
else:
    img_size = False

if not args.input:
    logging.warning("Input file must be specified...")
    exit(-1)

logging.info("Processing %s" % args.input)
regions = mmd.RegionFile.load(args.input)

output_dir = args.output
if args.movoutputdir:
    output_dir += "/" + regions.basename

# Create output directory
os.makedirs(output_dir,exist_ok=True)

r = { "transit": [] }

transit = False
transit_regions = []

for region in regions.regions():

    if region.static:


        if region.unknown:
            continue

        print(region.scene_tag)

        if not re.search('.*z0', region.scene_tag):
            continue

        if re.search('.*_p0_z0', region.scene_tag):
            transit = True
        else:
            transit = False
            if len(transit_regions) > 0:
                print("Have %d transit regions" % len(transit_regions))

                r["transit"] += transit_regions

        transit_regions = []


        # Take first instance of each scene tag
        if region.scene_tag in r:

            if args.flatten:
                continue

        else:
            r[region.scene_tag] = []

        r[region.scene_tag].append(region)

    else:

        if not transit:
            continue

        if re.match('[NSWE]*', region.type):
            transit_regions.append(region)



img_files = {}
scene_tags = {}

for key,rs in r.items():

    for region in rs:

        splits = [0.5]
        if key == "transit":
            splits = [0.25,0.5,0.75]


        for s in splits:
            sample_frame = region.start_frame + s * (region.end_frame - region.start_frame)

            basename = path.splitext(path.basename(regions.mov))[0]
            img_file = output_dir + "/" + "%s_%06d.%s" % (basename, sample_frame, args.imageext)

            img_files[region] = img_file

            if not region.scene_tag in scene_tags:
                scene_tags[region.scene_tag] = []

            scene_tags[region.scene_tag].append(img_file)

            if args.force or not path.exists( img_file ):
                logging.info("Fetching frame %d from %s for contact sheet" % (sample_frame, basename))

                if img_size:
                    img = qt.get_frame(regions.mov, sample_frame, format=args.imageext)
                    img.thumbnail(img_size)  # PIL.thumbnail preserves aspect rati
                    img.save(img_file)
                else:
                    # Save directly
                    qt.save_frame(regions.mov, sample_frame, img_file, format=args.imageext)


## Write an annotation file
json_file = output_dir + "/images.json"
with open(json_file, 'w') as f:
    json.dump(scene_tags, f, indent='  ')




# tags = []
# images = []
# urls = []
#
# gt_urls = []
#
# if args.groundtruth:
#     gt_library = ra.GroundTruthLibrary()
#     gt_library.load_ground_truth(args.groundtruthfile)
#
#     gt_path = random.sample(gt_library.regions.keys(), 1)
#
#     logging.info("Using ground truth image %s" % gt_path)
#
#     url = gt_library.urls[gt_path[0]]
#
#     for r in gt_library.regions[gt_path[0]].static_regions():
#         tags.append(r.scene_tag)
#         images.append({url: [r]})
#
#     urls.append(url)
#     gt_urls.append(url)
#
# unknowns = {}
#
#
# def scene_tag_match( a, b ):
#     ## Disregard deployment
#     astem = re.sub( r'd\d{1}_', "", a )
#     bstem = re.sub( r'd\d{1}_', "", b )
#
#     print("a    : %s;  b     = %s" % (a,b))
#     print("astem: %s;  bstem = %s" % (astem,bstem))
#
#     return astem == bstem
#
#
# def process( infile ):
#     logging.info("Processing %s" % infile)
#
#     regions = mmd.RegionFile.load(infile)
#
#     mov = regions.mov
#
#     # Skip if already processed  (handles ground truth files)
#     if  mov in urls:
#         return
#
#     urls.append(mov)
#
#     unknowns[mov] = []
#
#     idx = 0
#     prevTag = None
#     for r in regions.static_regions():
#
#         if r.unknown or not r.scene_tag:
#             unknowns[mov].append(r)
#             continue
#
#         # Squash runs...
#         if r.scene_tag == prevTag and not args.squashruns:
#             images[idx-1][mov].append(r)
#             continue
#
#         prevTag = r.scene_tag
#
#         logging.info("%s (%d,%d): %s" % (mov, r.start_frame, r.end_frame, r.scene_tag))
#
#         if idx >= len(images):
#             tags.append(r.scene_tag)
#             images.append({mov: [r]})
#         elif scene_tag_match(r.scene_tag, tags[idx]):
#             images[idx][mov] = [r]
#         else:
#             logging.info("Tag doesn't match order... (%s != %s)" % (r.scene_tag, tags[idx]))
#
#             MAX_JUMP = 5
#             success = False
#             for i in range(idx, min(idx+MAX_JUMP,len(tags))):
#                 logging.info("Checking %s against %s at %d" % (r.scene_tag, tags[i], i))
#                 if scene_tag_match(r.scene_tag, tags[i]):
#                     images[i][mov] = [r]
#                     idx = i
#                     success = True
#                     break
#
#             if not success:
#                 logging.info("Couldn't find a match, insert...")
#                 # Couldn't find match.   insert
#                 tags.insert(idx, r.scene_tag)
#                 images.insert( idx, {mov: [r]} )
#                 #idx = idx-1 # Back up so we reconsider using this new entry
#
#         # On success
#         idx += 1
#
#
# for pathin in args.input:
#     for infile in glob.iglob(pathin):
#
#         # Iterate again
#         if path.isdir(infile):
#             infile += "*_regions.json"
#             for f in glob.iglob(infile):
#                 process(f)
#         else:
#             process( infile )
#
#
# img_path  = path.dirname(args.outfile) + "/images/"
# os.makedirs(img_path, exist_ok=True)
#
# urls = sorted(urls)
#
# html_file = args.outfile
#
# logging.info("Saving to %s" % html_file)
#
# with open(html_file, 'w') as html:
#     html.write("<html><body>\n")
#     html.write("<h2>Proof sheet</h2>\n\n")
#
#     html.write("<table>\n<tr><th>Scene Tag</th>")
#     for name in urls:
#         if name in gt_urls:
#             html.write("<th>GROUND TRUTH<br>%s</th>" % path.basename(name))
#         else:
#             html.write("<th>%s</th>" % path.basename(name))
#
#
#     html.write("</tr>\n")
#     #><th>Reference image from class</th>\n")
#
#     for row in range(len(images)):
#         html.write("<tr>")
#         html.write("<td>%s</td>" % (tags[row]) )
#
#         for url in urls:
#             if url not in images[row]:
#                 html.write("<td></td>")
#                 continue
#
#             regions = images[row][url]
#
#             if len(regions) < 1:
#                 continue
#
#             region = regions[0]
#
#             sample_frame = region.start_frame + 0.5 * (region.end_frame - region.start_frame)
#
#             img_file = img_path + "%s_%d.%s" % (path.splitext(path.basename(url))[0], sample_frame, args.imageext)
#             thumb_file = img_path + "%s_%d_thumbnail.%s" % (path.splitext(path.basename(url))[0], sample_frame, args.imageext)
#
#             if args.force or not path.exists( img_file ) or not path.exists( thumb_file ):
#                 logging.info("Fetching frame %d from %s for contact sheet" % (sample_frame, path.basename(url)))
#                 img = qt.get_frame( url, sample_frame, format=args.imageext )
#                 img.save( img_file )
#                 img.thumbnail( img_size )  # PIL.thumbnail preserves aspect ratio
#
#                 img.save( thumb_file )
#
#             relapath = path.relpath( img_file, path.dirname(html_file) )
#             relathumb = path.relpath( thumb_file, path.dirname(html_file) )
#
#             caption = ', '.join(["%d -- %d" % (r.start_frame,r.end_frame) for r in regions])
#
#             html.write("<td><a href=\"%s\"><img src=\"%s\"/></a><br>%s</td>" % (relapath,relathumb,caption) )
#
#
#         html.write("</tr>")
#
#     # And unknowns (how's the DRY?)
#
#     # html.write("</table><hr>\n")
#     #
#     # html.write("<h2>Unidentified images</h2>")
#
#     html.write("<tr><th>Scene Tag</th>")
#     for name in urls:
#         html.write("<th>%s</th>" % path.basename(name))
#     html.write("</tr>\n")
#
#     html.write("<tr>")
#     html.write("<td>Unknown</td>" )
#
#     logging.info("Processing unknowns")
#
#     for url in urls:
#         if url not in unknowns:
#             html.write("<td></td>")
#             continue
#
#         html.write("<td>")
#         for region in unknowns[url]:
#
#             sample_frame = region.start_frame + 0.5 * (region.end_frame - region.start_frame)
#
#             img_file = img_path + "%s_%d.%s" % (path.splitext(path.basename(url))[0], sample_frame, args.imageext)
#             thumb_file = img_path + "%s_%d_thumbnail.%s" % (path.splitext(path.basename(url))[0], sample_frame, args.imageext)
#
#             if args.force or not path.exists( img_file ) or not path.exists( thumb_file ):
#                 logging.info("Fetching frame %d from %s for contact sheet" % (sample_frame, path.basename(url)))
#                 img = qt.get_frame( url, sample_frame, format='jpg' )
#                 img.save( img_file )
#                 img.thumbnail( img_size )  # PIL.thumbnail preserves aspect ratio
#
#                 img.save( thumb_file )
#
#             relapath = path.relpath( img_file, path.dirname(html_file) )
#             relathumb = path.relpath( thumb_file, path.dirname(html_file) )
#
#             html.write("<a href=\"%s\"><img src=\"%s\"/></a><br>%d -- %d<br>" % (relapath,relathumb,region.start_frame,region.end_frame) )
#         html.write("</td>")
#
#
#     html.write("</tr>")
#
#
#
#     # for r in jin["regions"]:
#     #
#     #     if r['type'] != "static":
#     #         continue
#     #
#     #     html.write("<tr>")
#     #     html.write("<td>%d</td><td>%d</td>" % (r['startFrame'], r['endFrame']) )
#     #
#     #     if "sceneTag" in r.keys():
#     #         html.write("<td>%s</td>" % r["sceneTag"])
#     #     else:
#     #         html.write("<td><<b>unclassified</b></td>")
#     #
#     #
#     #     img_file = img_path + "%d.png" % sample_frame
#     #     if args.force or not path.exists( img_file ):
#     #         logging.info("Fetching frame %d from %s for contact sheet" % (sample_frame, name))
#     #         img = qt.get_frame( url, sample_frame, format='png' )
#     #         img.save( img_file )
#     #
#     #     relapath = path.relpath( img_file, path.dirname(html_file) )
#     #     html.write("<td><img width=640 src=\"%s\"/></td>" % (relapath) )
#     #
#     #     # html.write("<td>")
#     #     # if "sceneTag" in r.keys() and len(r['sceneTag']) > 0:
#     #     #     first = r['sceneTag'][0]
#     #     #     if  first in classifier.tags():
#     #     #         paths = classifier.sample_paths( first, 3 )
#     #     #
#     #     #         relapaths = [ path.relpath(p, path.dirname(html_file) ) for p in paths]
#     #     #
#     #     #         for r in relapaths:
#     #     #             html.write("<img width=640 src=\"%s\"/>" % r)
#     #     #
#     #     # html.write("</td>")
#     #     html.write("</tr>\n")
#
#
#     html.write("</table>")
#     html.write("</body></html>")
