#! usr/bin/python
# ChenooViewer.py
# Contact: Jacob Schreiber
#			jmschrei@soe.ucsc.edu
#
# A GUI for analyzing nanopore data. Requires:
#   * numpy
#   * matplotlib
#   * PyPore
#   * mySQLdb
#   * PyQt4
#
# Please view README for tutorial.

import matplotlib
matplotlib.use( 'Qt4Agg')
matplotlib.rcParams['backend.qt4'] = 'PyQt4'

import sys
import numpy as np
from PyQt4 import QtGui as Qt
from PyQt4 import QtCore as Qc

from config import *
import time

from PyPore.parsers import *
from PyPore.database import *
from PyPore.DataTypes import *
from PyPore.hmm import *
from PyPore.alignment import *

from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QTAgg as NavigationToolbar
import matplotlib.pyplot as plt

class Logo( Qt.QLabel ):
    '''
    The Abada Logo. 
    '''
    def __init__( self, parent ):
        import os
        super( Logo, self ).__init__( parent )
        logo = Qt.QPixmap( os.getcwd() + r'\thumbs\\abadaLogo.png' )
        self.setPixmap( logo )
        self.show()

class Divider( Qt.QFrame ):
    '''
    A divider of a specific size, used to divide up menus.
    '''
    def __init__( self ):
        super( Divider, self ).__init__()
        self.setFrameStyle( Qt.QFrame.HLine | Qt.QFrame.Sunken )
        self.setLineWidth( 1 )
        self.setMidLineWidth( 1 )

class ConfirmWindow( Qt.QWidget ):
    '''
    This is a confirmation window, which takes in a message and a function. The
    message is displayed in the window, and the function is what is performed
    if the user chooses to confirm the action.
    '''
    def __init__( self, parent, errmsg, function ):
        Qt.QWidget.__init__( self )
        self.func = function
        confirmWidget = Qt.QPushButton( "Confirm" )
        quitWidget = Qt.QPushButton( "Quit" )

        grid = Qt.QGridLayout()
        grid.addWidget( Qt.QLabel( errmsg ), 0, 0, 1, 5 )
        grid.addWidget( confirmWidget, 2, 4 )
        grid.addWidget( quitWidget, 2, 5 )

        self.connect( confirmWidget, Qc.SIGNAL( "clicked()" ), function )
        self.setLayout( grid )
    def confirm( self ):
        '''Call the function and exit if the user confirms action.''' 
        self.function()

class ChenooViewer( Qt.QWidget ):
    '''
    The MySQL Database connector. This window will connect to the database specified
    in config.py and get all the table names. When a table is selected from the dropdown
    menu at the top, a table will be generated from the data. A menu will also be
    made from querying the columns in the table. Add, search, and delete are functions on
    all tables, while save files is a property on the table specified in config.py under
    SOURCE.
    '''
    def __init__( self, parent ):
        super( ChenooViewer, self ).__init__( parent )
        self.parent = parent
        self.db = MySQLDatabaseInterface( db=DATABASE, host=DATABASE_HOST, 
                                          password=DATABASE_PASSWORD, user=DATABASE_USER )
        self.tableView = Qt.QTableWidget()
        self.tableSelector = Qt.QComboBox()
        self.tableSelector.activated[ str ].connect( self._update )
        for table in self.db.read( "SHOW TABLES" ):
            self.tableSelector.addItem( table[0] )

        addButton = Qt.QPushButton( "Add" )
        searchButton = Qt.QPushButton( "Search" )
        deleteButton = Qt.QPushButton( "Delete" )
        queryButton = Qt.QPushButton( "SQL Query" )

        self.connect( addButton, Qc.SIGNAL("clicked()"), self._add )
        self.connect( searchButton, Qc.SIGNAL("clicked()"), self._search )
        self.connect( deleteButton, Qc.SIGNAL("clicked()"), self._delete_confirm )
        self.connect( queryButton, Qc.SIGNAL("clicked()"), self._build_view )

        self.inputGrid = Qt.QGridLayout()
        self.grid = Qt.QGridLayout()
        self.grid.setVerticalSpacing(0)
        self.grid.addWidget( self.tableSelector, 0, 0 )
        self.grid.addWidget( self.tableView, 1, 0, 10, 12 )
        self.grid.addLayout( self.inputGrid, 12, 0, 4, 10 )
        self.grid.addWidget( addButton, 12, 11 )
        self.grid.addWidget( searchButton, 13, 11 )
        self.grid.addWidget( deleteButton, 14, 11)
        self.query_input = Qt.QLineEdit()
        self.grid.addWidget( Divider(), 16, 0, 1, 12 )
        self.grid.addWidget( queryButton, 17, 11 )
        self.grid.addWidget( self.query_input, 17, 0, 1, 11 )

        self.setLayout( self.grid )
        self._update()

    def _update( self ):
        '''
        Update the table widget that is the view of the table. This will perform a
        search from the current parameters-- either of the specified table by using
        the menu, or across an arbitrary number of tables with the SQL Query line.
        '''
        for i in range( self.inputGrid.count() ): self.inputGrid.itemAt(i).widget().close()
        self.table = self.tableSelector.currentText()
        if self.table == DATABASE_SOURCE:
            self.saveButton = Qt.QPushButton( "Save Files" )
            self.connect( self.saveButton, Qc.SIGNAL("clicked()"), self._save_files )
            self.grid.addWidget( self.saveButton, 15, 11 )
        else:
            try:
                self.saveButton.close()
            except:
                pass

        self.columns = [ column[0] for column in self.db.read( "SHOW COLUMNS IN {}".format( self.table ))]
        self.column_inputs = { column: Qt.QLineEdit() for column in self.columns }
        self._search()
        self.inputGrid.setVerticalSpacing(0)

        for i, column in enumerate( self.columns ):
            label = Qt.QLabel( column )
            label.setAlignment( Qc.Qt.AlignCenter )
            self.inputGrid.addWidget( label, int(i/10)*2, i%10 )
            self.inputGrid.addWidget( self.column_inputs[ column ], int(i/10)*2+1, i%10 )
        if i < 10:
            while i < 10:
                self.inputGrid.addWidget( Qt.QLabel(""), 0, i )
                i += 1
            self.inputGrid.addWidget( Qt.QLabel(""), 3, 0 )

    def _search( self ):
        '''
        Gets the results of a query and updates the table widget with those
        results. 
        '''
        results = self._query_database()
        self.tableView.clear()
        self.tableView.setRowCount( MAX_DATABASE_SIZE )
        self.tableView.setColumnCount( len( self.columns ) )
        self.tableView.setHorizontalHeaderLabels( self.columns )
        i = 0
        for i in xrange( len( results ) ):
            for j in xrange( len( self.columns ) ):
                try:
                    cell = Qt.QTableWidgetItem( unicode( results[i][j] ) )
                    self.tableView.setItem( i, j, cell )
                except:
                    pass
        self.tableView.setRowCount( i+1 )
        self.tableView.setColumnCount( len( self.columns ) )

    def _get_input( self ):
        return ( self.column_inputs[ column ].text() or None for column in self.columns ) 

    def _add( self ):
        '''
        Take the entry from _get_input() and build an Entry object which can be
        committed to the database. NOTE: May change to have attribute-secure Entry
        with no NanoEntry. 
        '''
        self.db.insert( self.table, self._get_input() )

    def _build_clauses( self ):
        '''
        Builds a SQL query from user input, and returns that query. Currently all columns are returned
        for rows which are selected. No support is provided for projections yet. 
        '''
        column_data = self.db.read( "SHOW COLUMNS FROM {}".format(self.table) )
        columns = [ column[0] for column in column_data ]
        column_types = [ column[1] for column in column_data ] 

        entries = self._get_input()
        clauses = []
        for column, column_type, entry in zip( columns, column_types, entries ):
            if entry == None: # If nothing was entered into the field
                continue      # then do nothing 
            entry = entry.replace(" ", "") # Remove any extra white space that may be there
            if entry == "None": # If the entry is None, they're looking for empty cells
                clauses.append( "{column} IS NULL".format( column=column ) ) # Look where cell is null
            if 'varchar' in column_type: # If the cell type is a varchar
                if entry[-1] != '*':     # and they're looking for a wildcard, append the wildcard
                    clauses.append( "{column} = '{entry}'".format( column=column, entry=entry ) )
                else:
                    clauses.append( "{column} LIKE '%{entry}%'".format( column=column, 
                                                                        entry=entry[:-1] ) )
            elif 'float' in column_type or 'int' in column_type:
                clauses.append( "{column} = {entry}".format( column=column, entry=entry ) )

        return ' AND '.join( clauses ) or None 

    def _build_view( self ):
        query = str( self.query_input.text() )
        assert 'DROP' not in query.upper() and 'DELETE' not in query.upper() 
        self.columns = query.strip().split( "SELECT" )[1].split( "FROM" )[0].strip().split(",")
        self.tables = query.strip().split("FROM")[1].split("WHERE")[0].strip().split(",")
        if self.columns == ['*']:
            column_data = [ [ table+"."+column[0] for column 
                                in self.db.read( "SHOW COLUMNS FROM {}".format(table) ) ] 
                                for table in self.tables ]
            self.columns = np.concatenate( column_data )

    def _query_database( self ):
        clauses = self._build_clauses()
        if clauses:
            query = "SELECT * FROM {table} WHERE {clauses}".format( clauses=clauses, table=self.table )
        else:
            query = "SELECT * FROM {table}".format( table=self.table )
        return self.db.read( query )

    def _delete_confirm( self ):
        n = len( self._query_database() )
        errmsg = "Do you really want to delete {0} entr{1}?".format(n, ['y', 'ies'][n>1] )
        self.confirmWindow = ConfirmWindow( self, errmsg, self._delete )
        self.confirmWindow.show()

    def _delete( self ):
        del self.confirmWindow
        query = "DELETE FROM {table} WHERE {clauses}".format( table=self.table, 
                                                              clauses=self._build_clauses() )
        self.db.delete( query=query )
    
    def _save_files( self ):
        files = []
        for i in range( self.tableView.rowCount() ):
            filename = str( self.tableView.item( i, 0 ).text() )
            station = str( self.tableView.item( i, 3 ).text() )
            files.append( "{filename}-s0{station}".format( filename=filename, station=station ) )
        self.parent.saved_files = files

class DetectionWindow( Qt.QWidget ):
    '''
    This window gives options for event detection and segment detection, and specifying which files
    are to be analyzed. 
    '''
    def __init__( self, parent ):
        super( DetectionWindow, self ).__init__( parent )
        self.parent = parent
        self.eventDetectorOptions = { '': parser(), 
                                      'Lambda Parser': lambda_event_parser() }
        self.segmenterOptions =     { '': parser(), 
                                      'Snakebase Parser': snakebase_parser(), 
                                      'Novakker': novakker_parser(), 
                                      'StatSplit': StatSplit(), 
                                      'SpeedyStatSplit': SpeedyStatSplit() }
        self.eventDetector = ''
        self.segmenter = ''
        self.defaultGrid = Qt.QGridLayout()
        self.defaultGrid.addWidget( Qt.QLabel( "Default Settings Applied" ), 0, 0 )
                
        self.grid = Qt.QGridLayout()
        self.grid.setSpacing( 5 )

        self.fileList = Qt.QTableWidget() # Initialize the widget
        self.fileList.setRowCount( 20 ) # Set the maximum number of files allowed to analyze
        self.fileList.setColumnCount( 3 ) # Set the columns
        # Set the titles of those columns
        self.fileList.setHorizontalHeaderLabels( [ 'Filenames', ' Sample', 'Event Count' ] )
        # Set the filename to be longer than the others
        self.fileList.setItem( 0, 0, Qt.QTableWidgetItem( "Z://00x000000-s0x" ) )
        # Resize the widget to an appropriate column width given the filename
        self.fileList.resizeColumnsToContents()
        # Empty the widget
        self.fileList.setItem( 0, 0, Qt.QTableWidgetItem( "" ) )

        for i in xrange( len( parent.input_files) ):
            try:
                fileWidget = Qt.QTableWidgetItem( str( parent.input_files[i]))
                self.fileList.setItem( i, 0, fileWidget )
            except:
                continue
            try:
                sampleWidget = Qt.QTableWidgetItem( str( parent.input_files_samples[i]))
                self.fileList.setItem( i, 1, sampleWidget )
            except:
                pass
            try:
                nWidget = Qt.QTableWidgetItem( str( parent.input_files_n[i]))
                self.fileList.setItem( i, 2, nWidget )
            except:
                pass

        self.eventDetectMenu = Qt.QComboBox()
        self.eventDetectMenu.activated[ str ].connect( self._select_event_detector ) 
        for option in self.eventDetectorOptions:
            self.eventDetectMenu.addItem( option )
        self.segmenterMenu = Qt.QComboBox()
        self.segmenterMenu.activated[ str ].connect( self._select_segmenter )
        for option in self.segmenterOptions:
            self.segmenterMenu.addItem( option )

        self.eventDetectorGUI = self.defaultGrid
        self.segmenterGUI = self.defaultGrid

        self.grid.addWidget( self.fileList, 0, 0, 20, 1 )
        self.grid.addWidget( Qt.QLabel( "" ), 0, 2, 1, 30 ) 
        self.grid.addWidget( Qt.QLabel( "Event Detection" ), 0, 5, 1, 10 )
        self.grid.addWidget( self.eventDetectMenu, 1, 5, 1, 10 )
        self.grid.addWidget( Qt.QLabel( "Segmenter" ), 0, 15, 1, 10 )
        self.grid.addWidget( self.segmenterMenu, 1, 15, 1, 10 )

        load_file_button = Qt.QPushButton( "Load Files" )
        self.connect( load_file_button, Qc.SIGNAL( "clicked()" ), self._load_files )
        self.grid.addWidget( load_file_button, 20, 0 )

        self.grid.addWidget( Qt.QLabel( "Bessel Filter Options" ), 12, 5, 1, 10 )
        self.filterCheckBox = Qt.QCheckBox( "Filter Events" )
        self.orderInput = Qt.QLineEdit()
        self.orderInput.setText( "1" )
        self.filterInput = Qt.QLineEdit()
        self.filterInput.setText( "2000" )
        self.grid.addWidget( self.filterCheckBox, 13, 5, 1, 2 )
        self.grid.addWidget( self.filterInput, 13, 6, 1, 2 )
        self.grid.addWidget( Qt.QLabel( "Cutoff Frequency" ), 13, 8, 1, 5 )
        self.grid.addWidget( self.orderInput, 14, 6, 1, 2 )
        self.grid.addWidget( Qt.QLabel( "Order" ), 14, 8, 1, 5 )

        self.grid.addWidget( Qt.QLabel("Database Options"), 12, 15, 1, 10 )
        self.save_to_database = Qt.QCheckBox( "Save Analysis to Database" )
        self.grid.addWidget( self.save_to_database, 13, 15, 1, 10 )

        self.load_from_database = Qt.QCheckBox( "Try to Load Analysis from Database" )
        self.grid.addWidget( self.load_from_database, 14, 15, 1, 10 )
        self.load_from_database.setChecked(True)

        self.grid.addWidget( Qt.QLabel( "JSON Options"), 15, 15, 1, 10 )
        self.save_to_json = Qt.QCheckBox( "Save Analysis to JSON" )
        self.load_from_json = Qt.QCheckBox( "Load Analysis From JSON" )
        self.grid.addWidget( self.save_to_json, 16, 15, 1, 10 )
        self.grid.addWidget( self.load_from_json, 17, 15, 1, 10  )
        self.grid.addWidget( Qt.QLabel( "If you load, files must be in same file as Abada" ), 
                                                                                18, 15, 1, 10 )

        self.metaAnalysis = Qt.QCheckBox( "Only Store Metadata" )
        self.grid.addWidget( self.metaAnalysis, 18, 5, 1, 15 )
        self.analysisButton = Qt.QPushButton( "Analyze" )
        self.grid.addWidget( self.analysisButton, 19, 5 )

        self.outputButton = Qt.QPushButton( "Output" )
        self.grid.addWidget( self.outputButton, 19, 6 )

        self.progressBar = Qt.QProgressBar( self )
        self.grid.addWidget( self.progressBar, 20, 5, 1, 19 )
        self.timer = Qc.QBasicTimer()

        self.stopButton = Qt.QPushButton( "Stop" )
        self.grid.addWidget( self.stopButton, 20, 24 )
        self.connect( self.stopButton, Qc.SIGNAL("clicked()"), self._stop_analysis )
        self._active = False

        self.connect( self.outputButton, Qc.SIGNAL( "clicked()" ), self._output )
        self.connect( self.analysisButton, Qc.SIGNAL( "clicked()" ), self._analyze )
        self._load_files()
        self.setLayout( self.grid )

    def _select_event_detector( self, detector ):
        ''' This is what occurs when an event detector is selected. '''
        for i in range( self.eventDetectorGUI.count() ): 
            self.eventDetectorGUI.itemAt( i ).widget().close() 
        self.eventDetector = str(detector)
        self.eventDetectorGUI = self.eventDetectorOptions[str(detector)].GUI() or self.defaultGrid
        self.grid.addLayout( self.eventDetectorGUI, 2, 5, 1, 10 )

    def _select_segmenter( self, detector ):
        ''' This is what occurs when a segmenter is selected. ''' 
        for i in range( self.segmenterGUI.count() ): 
            self.segmenterGUI.itemAt( i ).widget().close() 
        self.segmenter = str(detector)
        self.segmenterGUI = self.segmenterOptions[str(detector)].GUI() or self.defaultGrid
        self.grid.addLayout( self.segmenterGUI, 2, 15, 1, 10 )

    def _load_files( self ):
        ''' Load the files which were saved from querying the database. '''
        for i, filename in enumerate( self.parent.saved_files ):
            self.fileList.setItem( i, 0, Qt.QTableWidgetItem( str( filename ) ) )

    def _read_input( self ):
        ''' Read the files which are put in to the table. ''' 
        files, samples = [], []
        i = 0
        while True:
            try:
                file = str( self.fileList.item( i, 0 ).text() )
                if file == '':
                    raise AttributeError
                files.append( str( self.fileList.item( i, 0 ).text() ).strip(".abf") )
                try:
                    sample = str( self.fileList.item( i, 1 ).text() )
                    if sample == '':
                        samples.append("Aggregate Data")
                    samples.append( str( self.fileList.item( i, 1 ).text() ) )
                except:
                    samples.append("Aggregate Data")
            except AttributeError:
                self.parent.input_files = files
                self.parent.input_files_samples = samples
                self.parent.input_files_n = []
                return files, samples 
            i += 1

    def _stop_analysis( self ):
        self._active=False

    def _analyze( self ):
        ''' 
        Analyze each file by calling event detectors on each file, then by possibly
        calling segmenters on each event. This stores all of the information to 
        the experiment graph.  
        '''
        self.parent.experiment.delete()

        # Load the event detector and set the appropriate parameters
        event_detector = self.eventDetectorOptions[ self.eventDetector ]
        event_detector.set_params()

        # Load the segmenter and set the appropriate parameters
        segmenter = self.segmenterOptions[ self.segmenter ]
        segmenter.set_params()

        # Read in the file and appropriate sample names 
        filenames, sample_names = self._read_input()

        # Create a mapping between the name of the sample, and the sample object
        smap = { sample_name: Sample( label=sample_name ) for sample_name in set(sample_names) }
        samples = smap.values()

        if self.filterCheckBox.checkState() == 2: # If filtering selected
            order = int( self.orderInput.text() ) 
            cutoff = float( self.filterInput.text() )
        else:
            order, cutoff = None, None 

        # Keep a list of all the files
        files = []

        self.progressBar.setValue(0)
        self.progressBar.setMaximum(1)
        self._active = True 
        # For every pair of filename, sample name in the table
        for i, ( sample_name, filename ) in enumerate( zip( sample_names, filenames ) ):
            sample = smap[ sample_name ]
            try:
                if self.load_from_database.checkState() == 2:
                    db_filename = filename.split("\\")[-1]
                    file = File.from_database( database=DATABASE, host=DATABASE_HOST,
                                               password=DATABASE_PASSWORD,
                                               user=DATABASE_USER,
                                               filename=db_filename,
                                               eventDetector=event_detector.__class__.__name__,
                                               eventDetectorParams=repr(event_detector),
                                               segmenter=segmenter.__class__.__name__,
                                               segmenterParams=repr(segmenter),
                                               filterCutoff=cutoff, filterOrder=order )
                elif self.load_from_json.checkState() == 2:
                    if filename.endswith( "json" ):
                        file = File.from_json( filename )
                    else:
                        file = File.from_json( filename+".json" )
                else:
                    raise Exception()

            except:
                file = File( filename+".abf" ) # Create a file object for one of the input files
                file.parse( parser=event_detector )
                if segmenter != '':
                    for j, event in enumerate( file.events ):
                        if not self._active:
                            break
                        if sample:
                            event.sample = sample
                        if order and cutoff:
                            event.filter( order=order, cutoff=cutoff )
                        event.parse( parser=segmenter )
                        self.progressBar.setValue( 1. + i * file.n + j ) 
                        self.progressBar.setMaximum( len(filenames )*file.n )
                        Qt.qApp.processEvents()
                        time.sleep( 0.001 )
            finally:
                if self.metaAnalysis.checkState() == 2:
                    file.to_meta()
                if self.save_to_database.checkState() == 2:
                    file.to_database( database=DATABASE, host=DATABASE_HOST,
                                      password=DATABASE_PASSWORD,
                                      user=DATABASE_USER )
                if self.save_to_json.checkState() == 2:
                    file.to_json( file.filename+".json" )

            files.append( file ) # Add that file to the list of files
            sample.files.append( file ) # Add the file to the appropriate sample

            time.sleep( 0.001 )
            self.progressBar.setValue( i+1 )
            self.fileList.setItem( i, 2, Qt.QTableWidgetItem( str( file.n ) ) )
            self.parent.input_files_n.append( file.n )
            self.progressBar.setMaximum( len(filenames) )
            Qt.qApp.processEvents()
            if not self._active:
                break

        self.parent.experiment = Experiment( filenames=[] )
        self.parent.experiment.files = files

    def _output( self ):
        '''
        Write out to a csv file all the data in an event, or a segment. 
        '''
        exp = self.parent.experiment # Unpack the experiment    
        events = exp.events # Store references to all the events
        with open( "abada_event_data.csv", "w" ) as out:
            # Write a csv file out that contains all the data
            out.write( "Filename,Sample,Start,Mean (pA),STD,Duration (s),Segment Count\n")
            for event in events:
                out.write("{filename},{sample},{start},{mean},{std},{duration},{segs}\n".format(
                                    filename=event.file.filename,
                                    sample=event.sample.label,
                                    start=event.start,
                                    mean=event.mean,
                                    std=event.std,
                                    duration=event.duration,
                                    segs=event.n ) )

        segments = exp.segments # Store references to all the states
        with open( "abada_segment_data.csv", "w" ) as out:
            # Write a csv file that contains all states 
            out.write( "Filename,Sample,Mean (pA),Start,STD,Duration (s)\n")
            for segment in segments:
                out.write( "{filename},{sample},{start},{mean},{std},{duration}\n".format(
                                filename=segment.event.file.filename,
                                sample=segment.event.sample.label,
                                start=segment.start + segment.event.start,
                                mean=segment.mean,
                                std=segment.std,
                                duration=segment.duration ) )

class EventViewerWindow( Qt.QWidget ):
    def __init__( self, parent ):
        super( EventViewerWindow, self ).__init__( parent )
        self.parent = parent
        self.events = self.parent.experiment.events
        grid = Qt.QGridLayout()
        grid.setVerticalSpacing(0)
        self.i = -1

        self.fig = plt.figure( facecolor='w', edgecolor='w' )
        self.canvas = FigureCanvas( self.fig )
        self.canvas.setParent( self )
        self.toolbar = NavigationToolbar( self.canvas, self )

        self.markButton = Qt.QCheckBox( "Exclude" )
        self.connect( self.markButton, Qc.SIGNAL( "clicked()" ), self._mark )
        grid.addWidget( self.markButton, 5, 9 )

        nextPlotButton = Qt.QPushButton( "Plot Next" )
        self.connect(nextPlotButton, Qc.SIGNAL( "clicked()" ), lambda: self._move( direction=1 ) )
        previousPlotButton = Qt.QPushButton( "Plot Previous" )
        self.connect(previousPlotButton, Qc.SIGNAL("clicked()"), lambda: self._move(direction=-1))
        currentPlotButton = Qt.QPushButton( "Replot" )
        self.connect(currentPlotButton, Qc.SIGNAL( "clicked()"), self._plot )

        grid.addWidget( nextPlotButton, 5, 0  )
        grid.addWidget( previousPlotButton, 6, 0 )
        grid.addWidget( currentPlotButton, 7, 0 )

        self.colorGroup = Qt.QButtonGroup()
        bawCheckBox = Qt.QRadioButton( "Black and White" )
        colorCheckBox = Qt.QRadioButton( "Color" )
        hmmCheckBox = Qt.QRadioButton( "HMM Hidden States")
        self.colorGroup.addButton( bawCheckBox, 0 )
        self.colorGroup.addButton( colorCheckBox, 1 )
        self.colorGroup.addButton( hmmCheckBox, 2 )

        grid.addWidget( bawCheckBox, 5, 1 )
        grid.addWidget( colorCheckBox, 6, 1 )
        grid.addWidget( hmmCheckBox, 7, 1 )

        self.hmmDropBox = Qt.QComboBox()
        for key in self.parent.hmms.keys():
            self.hmmDropBox.addItem( key )
        grid.addWidget( self.hmmDropBox, 7, 2 )

        grid.addWidget( Qt.QLabel( "Filename: " ), 5, 6 )
        grid.addWidget( Qt.QLabel( "Time: " ), 6, 6 )
        grid.addWidget( Qt.QLabel( "Sample Label: " ), 7, 6 )

        self.eventFilename = Qt.QLabel( "" )
        self.eventTime = Qt.QLabel( "" )
        self.eventSample = Qt.QLabel( "" ) 

        grid.addWidget( self.eventFilename, 5, 7 )
        grid.addWidget( self.eventTime, 6, 7 )
        grid.addWidget( self.eventSample, 7, 7 )

        grid.addWidget( Qt.QLabel( "Mean: " ), 5, 4 )
        grid.addWidget( Qt.QLabel( "Duration: "), 6, 4 )
        grid.addWidget( Qt.QLabel( "Segment Count: " ), 7, 4 )

        self.eventMean = Qt.QLabel( "" )
        self.eventDuration = Qt.QLabel( "" )
        self.eventStateCount = Qt.QLabel( "" )

        grid.addWidget( self.eventMean, 5, 5 )
        grid.addWidget( self.eventDuration, 6, 5 )
        grid.addWidget( self.eventStateCount, 7, 5 )

        grid.addWidget( self.canvas, 0, 0, 4, 10 )
        grid.addWidget( self.toolbar, 4, 0, 1, 10 )
        self.setLayout( grid )

    def _mark( self ):
        if self.markButton.checkState() == 0:
            for i in range( len( self.parent.marked_event_indices ) ):
                if self.parent.marked_event_indices[i] == self.i:
                    del self.parent.marked_event_indices[i]
                    break
        elif self.markButton.checkState() == 2:
            self.parent.marked_event_indices.append( self.i )

    def _move( self, direction ):
        '''
        Moves the current event being shown in the direction specified. Must enter
        direction as either -1 or 1. 
        '''
        assert np.abs( direction ) == 1
        n = len( self.parent.experiment.events )
        if ( self.i > 0 or direction == 1 ) and ( self.i < n - 1 or direction == -1 ):
            self.i += direction
        self._plot()

    def _plot( self ):
        '''
        Plots the current image, at index self.i. If indicated, will color either by hmm or states.
        If colored by hmm, it will color each segment by which hidden state the segment most likely
        belongs to. If colored by state, it will color each segment according to a color cycle of
        a few colors. 
        '''
        self.fig.clf() # Make it so the next plotting event removes the current plot 
        event = self.events[ self.i ] # Pull the next event

        # Remember if the user marked the event as a bad one or not
        if self.i in self.parent.marked_event_indices:
            self.markButton.setCheckState( 2 )
        else:
            self.markButton.setCheckState( 0 )

        if event != None:
            # If Black and White plot selected, or no states are stored to the event
            if self.colorGroup.checkedId() == 0 or event.n == 'N/A':
                event.plot( color='k' )

            # If color was selected, and states are present in the event
            elif self.colorGroup.checkedId() == 1:
                event.plot( color='cycle', alpha=0.75 )

            # If color-by-hmm was selected, and states are present 
            elif self.colorGroup.checkedId() == 2:
                hmm = self.parent.hmms[ str(self.hmmDropBox.currentText() ) ]
                event.plot( hmm=hmm, color='hmm' )

            plt.title( "Event {i}: in {filename} at {time}s".format( i=self.i+1, 
                                                                     filename=event.file.filename, 
                                                                     time=round(event.start, 2)))
            self.canvas.draw()

            self.eventFilename.setText( Qc.QString( event.file.filename ) )
            self.eventTime.setText( Qc.QString( str( round( event.start, 2 ) ) + " s" ) )
            try:
                self.eventSample.setText( Qc.QString( event.sample.label ) )
            except:
                pass
            self.eventMean.setText( Qc.QString( str( round( event.mean, 2 ) ) + " pA" ) ) 
            self.eventDuration.setText( Qc.QString( str( round( event.duration, 2 ) ) + " s" ) )
            self.eventStateCount.setText( Qc.QString( str( event.n ) ) )

class AnalysisWindow( Qt.QWidget ):
    '''
    This window is for displaying basic statistical information from the segments gathered in
    the previous windows, whether they be from an event detector, state detector, or a HMM.
    The statistics are gathered through the use of a dictionary of lambda expressions stored 
    to self.axes. 
    '''
    def __init__( self, parent ):
        super( AnalysisWindow, self ).__init__( parent )
        self.parent = parent
        self.last_datatype = None # Store the last attempt to plot, in case only recoloring is needed
        try: # Find indices which are unmarked by reversing the marked list
            n = len( self.parent.experiment.events ) 
            self.parent.unmarked_event_indices = [ i for i in xrange( n ) 
                                                   if i not in self.parent.marked_event_indices ]
        except: # If no marked list exists, or no experiment exists, do not plot anything
            self.parent.unmarked_event_indices = [] 

        self.hmmDropBox = Qt.QComboBox()
        for name in self.parent.hmms.keys():
            self.hmmDropBox.addItem( name )

        # Store the functions which gather statistical information as lambda expressions requiring
        # two keys to get to it-- the type and the statistical information. 

        unmarked = self.parent.unmarked_event_indices
        hmm = str( self.hmmDropBox.currentText() )

        exp = self.parent.experiment
        try:
            events = [ event for i, event in enumerate( exp.events ) if i in unmarked ]
        except:
            events = []

        try:
            segs = reduce( list.__add__, [ event.segments for event in events ] )
        except:
            segs = []

        self.axes = { 'event': { 
                        'Duration (s)': np.array([event.duration for event in events]), 
                        'Mean (pA)': np.array([event.mean for event in events]),
                        'Segment Count': np.array([event.n for event in events]),
                        'Count': None
                        },
                      'segment': {
                        'Duration (s)': np.array( [seg.duration for seg in segs] ),
                        'Mean (pA)': np.array( [seg.mean for seg in segs]),
                        'STD (pA)' : np.array( [seg.std for seg in segs] ),
                        'Count': None
                        }
                    }
        grid = Qt.QGridLayout()

        # Initiate the event plotting dropdown boxes
        self.event_xaxis = self._init_axis( plot_type='event' )
        self.event_yaxis = self._init_axis( plot_type='event' )
        self.event_display = Qt.QPushButton( "Plot!" )

        # Initiate the state plotting dropdown boxes
        self.segment_xaxis = self._init_axis( plot_type='segment' )
        self.segment_yaxis = self._init_axis( plot_type='segment' )
        self.segment_display = Qt.QPushButton( "Plot!" )

        self.fig = plt.figure( facecolor = 'w', edgecolor = 'w' )
        self.canvas = FigureCanvas( self.fig )
        self.canvas.setParent( self )
        self.subplot = self.fig.add_subplot( 111 )
        self.toolbar = NavigationToolbar( self.canvas, self )

        grid.addWidget( Qt.QLabel( "Plot Events"), 0, 6 )
        grid.addWidget( Qt.QLabel( "X Axis: " ), 1, 6 )
        grid.addWidget( Qt.QLabel( "Y Axis: " ), 2, 6 )
        grid.addWidget( self.event_xaxis, 1, 7 )
        grid.addWidget( self.event_yaxis, 2, 7 )
        grid.addWidget( self.event_display, 3, 7 )

        grid.addWidget( Divider(), 5, 5, 1, 5 )

        grid.addWidget( Qt.QLabel( "Plot Segments" ), 6, 6 )
        grid.addWidget( Qt.QLabel( "X Axis: " ), 7, 6 )
        grid.addWidget( Qt.QLabel( "Y Axis: " ), 8, 6 )
        grid.addWidget( self.segment_xaxis, 7, 7 )
        grid.addWidget( self.segment_yaxis, 8, 7 )
        grid.addWidget( self.segment_display, 9, 7 )

        grid.addWidget( Divider(), 11, 5, 1, 5 )

        grid.addWidget( Divider(), 18, 5, 1, 5 )
        grid.addWidget( Qt.QLabel( "Color By:" ), 19, 5 )
        self.colorByDropdown = Qt.QComboBox()
        self.colorByDropdown.addItem( "Uniform Cyan" )
        self.colorByDropdown.addItem( "Filename" )
        self.colorByDropdown.addItem( "Sample" )

        color = lambda: self._color( color_scheme = str( self.colorByDropdown.currentText()))
        self.colorByDropdown.activated[str].connect( color ) 
        grid.addWidget( self.colorByDropdown, 19, 6, 1, 3)

        self.connect( self.event_display, Qc.SIGNAL( "clicked()" ), 
                        lambda: self._plot( datatype = 'event' ) )
        self.connect( self.segment_display, Qc.SIGNAL( "clicked()" ), \
                        lambda: self._plot( datatype = 'segment' ) )

        grid.addWidget( self.canvas, 0, 0, 25, 5 )
        grid.addWidget( self.toolbar, 25, 0, 1, 5 )
        self.setLayout( grid )

    def _init_axis( self, plot_type ):
        axis = Qt.QComboBox()
        for option in self.axes[plot_type]:
            axis.addItem( option )
        return axis   

    def _plot( self, datatype, color='c'  ):
        '''
        The plotting function. Is responsible for gathering inputs from all input widgets, and
        then plotting those things. Can take in a 'color' argument indicating how to color the
        points that it sees. Datatype refers to either event, segments, or hmm, and is indicated
        by which 'plot' button was pressed on the GUI.
        '''
        # Wipe the current screen, but then allow overlapping plots
        self.subplot.hold( False )
        self.subplot.plot( [0,0], [0,0] )
        self.subplot.hold( True )

        # If plotting events, get input from the event widgets
        if datatype == 'event':
            xaxis = str( self.event_xaxis.currentText() )
            yaxis = str( self.event_yaxis.currentText() )
        # If plotting segments, get input from the segment widgets
        elif datatype == 'segment':
            xaxis = str( self.segment_xaxis.currentText() )
            yaxis = str( self.segment_yaxis.currentText() )
        # If plotting hmm states, get input from those widgets
        elif datatype == 'hmm':
            xaxis = str( self.hmm_xaxis.currentText() )
            yaxis = str( self.hmm_yaxis.currentText() ) 
        # If something else, a bad call and do nothing
        else:
            return

        # Store the last datatype, in case recoloring is done

        # If x-axis is count, create a horizontal histogram
        if xaxis == 'Count':
            # Gather data
            try:
                if last_datatype != datatype or last_xaxis != xaxis or last_yaxis != yaxis:
                    y = self.axes[ datatype ][ yaxis ]
                else: # If everything is the same, load up the previously stored data
                    y = self.last_y
            except: # If some variables do not exist, then assume first round
                y = self.axes[ datatype ][ yaxis ]
            
            # Color correctly
            if len(color) == 1:
                self.subplot.hist( y, fc=color, alpha=0.3, bins=25, 
                                        orientation='horizontal', label = "Aggregate Data" )
            else:
                for c in set( color ):
                    self.subplot.hist( y[ np.where( color == c )[0] ], 
                                        fc=c, alpha=0.3, bins=25, orientation='horizontal', 
                                        label = self.lmap[c] )

        # If y-axis is count, create a vertical histogram
        elif yaxis == 'Count':
            try:
                # Gather the x axis-- if it is the same axes as before, instead of recalculating
                # each point, use the previously stored data. Otherwise calculate the points for
                # the x axis. 
                if last_datatype != datatype or last_xaxis != xaxis or last_yaxis != yaxis:
                    x = self.axes[ datatype ][ xaxis ]
                else: 
                    x = self.last_x
            except:
                x = self.axes[ datatype ][ xaxis ]
            
            # Color the histogram according to if a single, or multiple, colors are given.
            if len(color) == 1:
                self.subplot.hist( x, fc=color, alpha=0.3, bins=25, label = "Aggregate Data" )
            else:
                self.subplot.hist( [ x[ np.where( color == c )[0] ] for c in set( color )  ],
                                    color=[ c for c in set( color ) ], alpha=0.4, bins=25, 
                                    label = [ self.lmap[c] for c in set( color ) ],
                                    stacked=True, fill=True ) 

        # If not ploting histograms, plot a scatterplot
        else:
            try:
                # Gather the x and y axis-- if it is the same axes as before, instead of
                # recalculating them, use the previous x axis or y axis. This will speed
                # up coloring options.
                if last_datatype != datatype: 
                    if last_xaxis != xaxis:
                        x = self.axes[ datatype ][ xaxis ]
                    else:
                        x = self.last_x
                    if last_yaxis != yaxis:
                        y = self.axes[ datatype ][ yaxis ]
                    else:
                        y = self.last_y 
            except:
                x = self.axes[ datatype ][ xaxis ]
                y = self.axes[ datatype ][ yaxis ]

            # Color the histogram according to if a single, or multiple, colors are given.
            if len(color) == 1:
                self.subplot.scatter( x, y, color=color, s=3, marker='o', label = "Aggregate Data"  )
            else:
                for c in set( color ):
                    self.subplot.scatter( x[ np.where( color == c )[0] ], y[ np.where( color == c )[0] ], 
                                            s=3, color=c, marker='o', label = self.lmap[c]  )

        # Set the legend and axes, then draw the image
        self.subplot.legend( loc = "best", numpoints = 1 )
        self.subplot.set_xlabel( xaxis )
        self.subplot.set_ylabel( yaxis )
        self.canvas.draw()

        # Save the last axes and data in case of recoloring
        self.last_datatype = datatype
        self.last_xaxis = xaxis
        self.last_yaxis = yaxis
        try:
            self.last_x = x
        except:
            pass
        try:
            self.last_y = y
        except:
            pass

    def _color( self, color_scheme ):
        '''
        Given different inputs for how to color a dataset, will produce the list of colors
        from the color cycle which correspond to the grouping selected. Must return a list
        of colors of the same length as the list of points, and must set self.fmap to be a
        mapping between the colors, and the name of the group to be displayed. 
        '''
        # Set up references to stored data to make calls less long
        exp = self.parent.experiment
        indices = self.parent.unmarked_event_indices
        events = [ event for i, event in enumerate( exp.events ) if i in indices ]
        segments = reduce( list.__add__, [ event.segments for event in events ] )

        # A 10 color color-cycle, assuming that there are only 10 possible groups
        color_cycle = [ 'r', 'b', 'g', 'm', 'c', 'w', 'k', 'y', '0.25', '0.75' ]

        # Uniform cyan, unless otherwise specified
        colors = 'c'

        # If they select the filename grouping..
        if color_scheme == 'Filename':
            files = exp.files
            cmap = { file.filename: color_cycle[i%len(color_cycle)+1] for i, file in enumerate( files ) }
            self.lmap = { value: key for key, value in cmap.items() }
            if self.last_datatype == 'event':
                colors = np.array( [ cmap[ event.file.filename ] for event in events ] )
            elif self.last_datatype == 'segment': 
                colors = np.array( [ cmap[ seg.event.file.filename ] for seg in segments ] )

        # If the user selects the sample grouping..
        elif color_scheme == 'Sample':
            samples = exp.samples
            cmap = { sample.label: color_cycle[i] for i, sample in enumerate( samples ) }
            self.lmap = { value: key for key, value in cmap.items() }
            if self.last_datatype == 'event':
                colors = np.array( [ cmap[ event.sample.label ] for event in events ] )
            elif self.last_datatype == 'segment':
                colors = np.array( [ cmap[ seg.event.sample.label ] for seg in segments ] )

        # Call plot again, giving an explicit color mapping
        self._plot( self.last_datatype, colors )

class HMMImportWindow( Qt.QWidget ):
    '''
    Allows you to import a HMM from a text file, and specify a few ways of
    making the model.
    '''

    def __init__( self, parent ):
        '''
        Set up the import window.
        '''
        
        super( HMMImportWindow, self ).__init__( parent )
        self.parent = parent

        self.fig = plt.figure( facecolor='w', edgecolor='w' )
        self.canvas = FigureCanvas( self.fig )
        self.canvas.setParent( self )
        self.toolbar = NavigationToolbar( self.canvas, self )
        self.subplot = self.fig.add_subplot( 111 )

        grid = Qt.QGridLayout()

        self.hmmFile = Qt.QLineEdit()
        importButton = Qt.QPushButton( "Import HMM" )
        self.connect( importButton, Qc.SIGNAL("clicked()"), self._import )
        grid.addWidget( Qt.QLabel( "HMM File: " ), 0, 1 )
        grid.addWidget( self.hmmFile, 0, 2, 1, 2 )
        grid.addWidget( importButton, 2, 0 )
        grid.addWidget( Qt.QLabel( "Please use full path (e.g. 'C:\Users\jmschrei\Desktop\hmm.txt') "), 0, 4 )

        grid.addWidget( Qt.QLabel( "HMM Name: " ), 1, 1 )

        self.name = Qt.QLineEdit()
        self.name.setText( "Test HMM" )
        grid.addWidget( self.name, 1, 2, 1, 2 )

        grid.addWidget( self.canvas, 3, 0, 20, 10 )
        grid.addWidget( self.toolbar, 23, 0, 1, 10 )

        self.setLayout( grid )

    def _import( self ):
        '''
        Organizes everything which occurs when the import button is hit. Builds a new HMM
        and sticks it to the parent HMM dictionary.
        '''

        name = self.name.text()
        distributions = self._read( self.hmmFile.text() )

        hmm = ModularProfileModel( NanoporeGlobalAlignmentModule, 
                                   distributions, 
                                   str(name), 
                                   insert=UniformDistribution(0,100) )
        self.parent.hmms[ str(name) ] = hmm
        self._draw_hmm( distributions )

    def _read( self, filename ):
        '''
        Reads in a properly formatted HMM generation file. All files must be line separated
        distribution objects of proper python syntax, such as the following:


        # This file stores the distributions of construct X
        # Contact: Jacob Schreiber
        #          jmschreiber@gmail.com
        NormalDistribution( 4, 2 )
        NormalDistribution( 2, 7 )
        NormalDistribution( 2, 3 )
        InverseGammaDistribution( 1, 0.5 )
        GaussianKernelDensity( [ 0.4, 0.6, 0.3, 0.2, 0.6 ], bandwidth=0.5 )
        GaussianKernelDensity( [ 6, 7, 6, 6.5, 6.4, 7.2, 4.1 ], bandwidth=0.1 )
        LambdaDistribution( lambda x: 4 <= x <= 6 )
        '''

        with open( filename, 'r' ) as infile:
            return map( eval, filter( lambda line: not line.startswith( '#' ), infile ) )

    def _draw_hmm( self, distributions ):
        '''
        Draw an example of the consensus event.
        '''
        plt.cla()
        plt.title( "Probability Map For {}".format( str(self.name.text()) ) )
        plt.ylabel( "pA" )
        plt.xlabel( "Index" )
        view = np.arange( 0, 120, .05 )

        for i, distribution in enumerate( distributions ):
            density = np.exp( map( distribution.log_probability, view ) )
            for v, d in zip( view, density ):
                if d > .01:
                    self.subplot.plot( [i, i+1], [v, v], c='b', linewidth=2, alpha=d )
        self.canvas.draw() 

class MainPage( Qt.QMainWindow ):
    '''
    The main page of the application is the background to all of the 'viewer' windows. It will
    hold information which is passed between the various windows, but is primarily seen as the
    toolbar on the top. This holds data such as the experiment tree and marked event indices 
    for removal.
    '''
    def __init__( self ):
        super( MainPage, self ).__init__()
        self.experiment = Experiment( filenames=[] )
        self.marked_event_indices = []
        self.unmarked_event_indices = []
        self.saved_files = []
        self.input_files = []
        self.hmms = hmm_factory

        self.setGeometry( 300, 300, 800, 500 )
        self.currentWindow = Logo( self )
        self.setCentralWidget( self.currentWindow )

        chenooViewer = Qt.QAction( Qt.QIcon( r'thumbs\db.png' ), 'Database Viewer', self )
        chenooViewer.setStatusTip( 'Chenoo Viewer' )
        chenooViewer.triggered.connect( lambda: self.setCentralWidget( ChenooViewer( self ) ) )

        detectionViewer = Qt.QAction( Qt.QIcon( r'thumbs\aW.png' ), 'Detection', self )
        detectionViewer.setStatusTip( 'Analysis Pipeline Viewer' )
        detectionViewer.triggered.connect( lambda: self.setCentralWidget( DetectionWindow(self)))   

        eventViewer = Qt.QAction( Qt.QIcon( r'thumbs\eV.png' ), 'Event Viewer', self )
        eventViewer.setStatusTip( 'Event Viewer' )
        eventViewer.triggered.connect( lambda: self.setCentralWidget( EventViewerWindow( self ) ) )

        analysisViewer = Qt.QAction( Qt.QIcon( r'thumbs\aV.png' ), 'Analysis Viewer', self )
        analysisViewer.setStatusTip( 'Analysis Viewer' )
        analysisViewer.triggered.connect( lambda: self.setCentralWidget( AnalysisWindow( self ) ) )

        # ALIGNMENT HAS BEEN TAKEN OUT WHILE ITS USE IS EVALUATED.
        #alignerViewer = Qt.QAction( Qt.QIcon( r'thumbs\align.png' ), 'Alignment Viewer', self )
        #alignerViewer.setStatusTip( 'Alignment Viewer' )
        #alignerViewer.triggered.connect( lambda: self.setCentralWidget( AlignmentWindow( self ) ) )

        hmmViewer = Qt.QAction( Qt.QIcon( r'thumbs\hmm.png' ), 'HMM Importer', self )
        hmmViewer.setStatusTip( 'HMM Importer' )
        hmmViewer.triggered.connect( lambda: self.setCentralWidget( HMMImportWindow( self ) ) )

        toolbar = self.addToolBar('Exit')
        toolbar.addAction( chenooViewer )
        toolbar.addAction( detectionViewer )
        toolbar.addAction( eventViewer ) 
        toolbar.addAction( analysisViewer )
        #toolbar.addAction( alignerViewer )
        toolbar.addAction( hmmViewer )
                
        self.setToolTip('Abada: The PyPore Data Analysis Pipeline')
        self.setWindowTitle('Abada')
        self.show()
        sys.exit( app.exec_() )

if __name__ == '__main__':
    import sys
    app = Qt.QApplication( sys.argv )
    MainPage()
    sys.exit( app.exec_() )